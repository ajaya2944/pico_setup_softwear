import uiautomator2 as u2
import time
import traceback # For detailed error logging

# --- Helper Functions (Many are the same as before) ---
# Connect to device (Do this once at the start of the script if not in main)
# device = u2.connect() # Moved to main to allow script to be imported
# device.implicitly_wait(5)

def wait_for_element_to_exist(d, selector, timeout=5, interval=0.3):
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            if d(**selector).exists:
                return True
        except u2.exceptions.UiObjectNotFoundError:
            pass
        except Exception as e:
            print(f"⚠️ Error checking existence for {selector}: {str(e)}")
        time.sleep(interval)
    return False

def wait_for_element_clickable(d, selector, timeout=10, interval=0.5):
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            element = d(**selector)
            if element.exists and element.info.get('clickable', False):
                return True
        except u2.exceptions.UiObjectNotFoundError:
            pass
        except Exception as e:
            print(f"⚠️ Error checking clickability for {selector}: {str(e)}")
        time.sleep(interval)
    return False

def click_element(d, selector, description="", timeout=10, post_click_delay=1.5):
    print(f"Attempting to click: {description or str(selector)}")
    if wait_for_element_clickable(d, selector, timeout=timeout):
        try:
            d(**selector).click()
            print(f"👍 Clicked (directly clickable match): {description or str(selector)}")
            if post_click_delay > 0: time.sleep(post_click_delay)
            return True
        except Exception as e:
            print(f"❌ Error clicking (even though found clickable) {description or str(selector)}: {str(e)}")
    
    # Fallback for non-directly clickable elements (e.g., text within a clickable container)
    if 'clickable' not in selector or not selector.get('clickable'):
        print(f"   INFO: Direct clickable match failed for {selector}. Trying existence + parent heuristic...")
        existence_timeout = max(timeout / 2, 3) 
        if wait_for_element_to_exist(d, selector, timeout=existence_timeout):
            try:
                d(**selector).click() 
                print(f"👍 Clicked (via existence + parent heuristic): {description or str(selector)}")
                if post_click_delay > 0: time.sleep(post_click_delay)
                return True
            except Exception as e:
                print(f"❌ Error clicking (via existence + parent heuristic) {description or str(selector)}: {str(e)}")
        else:
            print(f"   INFO: Element {selector} not found (for existence check).")
            
    print(f"🚫 Element not successfully clicked: {description or str(selector)}")
    return False

def handle_popups_with_retry(d, max_attempts=3, popup_definitions=None):
    if not popup_definitions:
        print("INFO: No popup definitions provided for handling.")
        return False
    CRITICAL_TYPES = ["confirm", "confirm_alt", "no thanks", "allow"] # "allow" is critical for permissions

    has_mandatory_critical_popup = any(
        p.get("type", "").lower() in CRITICAL_TYPES and not p.get("optional", True)
        for p in popup_definitions
    )
    actioned_mandatory_critical_popup_this_call = False
    any_action_taken_ever = False 

    for attempt in range(max_attempts):
        # Log construction (omitted for brevity, same as before)
        print(f"Popup handling attempt {attempt + 1}/{max_attempts}...")
        action_taken_this_attempt = False
        for popup_info in popup_definitions: 
            selector = {}
            selector_desc = "Unknown"
            if "textMatches" in popup_info: selector = {"textMatches": popup_info["textMatches"]}; selector_desc = f"textMatches='{popup_info['textMatches']}'"
            elif "text" in popup_info: selector = {"text": popup_info["text"]}; selector_desc = f"text='{popup_info['text']}'"
            elif "resourceId" in popup_info: selector = {"resourceId": popup_info["resourceId"]}; selector_desc = f"id='{popup_info['resourceId']}'"
            else: continue
            
            popup_type_from_def = popup_info.get("type", "info")
            popup_type_internal = popup_type_from_def.lower()
            popup_wait = popup_info.get("wait", 1.0)
            popup_click_timeout = popup_info.get("click_timeout", 5) # Reduced default for faster checks
            is_optional_popup = popup_info.get("optional", True) 
            
            if click_element(d, selector, f"Popup '{selector_desc}' (Type: {popup_type_from_def})", timeout=popup_click_timeout, post_click_delay=popup_wait):
                print(f"   ✅ Actioned: {selector_desc}")
                any_action_taken_ever = True; action_taken_this_attempt = True
                if popup_type_internal in CRITICAL_TYPES: 
                    print(f"   🎉 Critical type popup '{selector_desc}' handled.")
                    if not is_optional_popup: actioned_mandatory_critical_popup_this_call = True
                    return True 
                break 
        if action_taken_this_attempt and not has_mandatory_critical_popup: return True
        if not action_taken_this_attempt and attempt < max_attempts - 1: time.sleep(1) 
    
    if actioned_mandatory_critical_popup_this_call: return True
    if has_mandatory_critical_popup and not any_action_taken_ever: return False
    if has_mandatory_critical_popup and any_action_taken_ever and not actioned_mandatory_critical_popup_this_call: return False
    if any_action_taken_ever: return True
    return False

def scroll_and_click_once(d, target_texts_or_selectors, description="", scroll_steps=30, max_scroll_attempts=3, initial_check_timeout=2, scroll_to_end_first=False):
    print(f"📜 Scrolling to find and click: {description or target_texts_or_selectors}")

    def attempt_click(item):
        if isinstance(item, str): # If it's a string, assume it's text
            if click_element(d, {"text": item}, f"{description} (exact: '{item}')", timeout=initial_check_timeout): return True
            if click_element(d, {"textContains": item}, f"{description} (contains: '{item}')", timeout=initial_check_timeout): return True
        elif isinstance(item, dict): # If it's a selector dictionary
            if click_element(d, item, f"{description} (selector: {item})", timeout=initial_check_timeout): return True
        return False

    # Initial check without scrolling
    for item in target_texts_or_selectors:
        if attempt_click(item): return True

    if scroll_to_end_first:
        print(f"   Attempting to scroll to end first for '{description}'...")
        try:
            scrollable = d(scrollable=True)
            if scrollable.exists(timeout=1):
                scrollable.fling.toEnd(max_swipes=15) # Increased max_swipes
                time.sleep(1.5)
                # After scrolling to end, check for elements again
                for item in target_texts_or_selectors:
                    if attempt_click(item): return True
            else:
                print("   No scrollable view found to scroll to end.")
        except Exception as e:
            print(f"   Error scrolling to end: {e}")
        # If scroll_to_end_first is true, we might not want to do more step-by-step scrolling
        # Or we could, depends on the desired behavior. For now, if it's scroll_to_end, this is the main scroll attempt.

    # If not found or not scroll_to_end_first, proceed with step-by-step scrolling
    if not scroll_to_end_first or not any(attempt_click(item) for item in target_texts_or_selectors): # Recheck if not found after fling
        for scroll_attempt in range(max_scroll_attempts):
            print(f"   Scrolling step-by-step... (attempt {scroll_attempt + 1}/{max_scroll_attempts})")
            try:
                scrollable = d(scrollable=True)
                if not scrollable.exists(timeout=1):
                    print("   No scrollable element found for step scrolling.")
                    return False # Cannot scroll
                scrollable.scroll.vert.forward(steps=scroll_steps)
                time.sleep(1.5)
            except Exception as e: 
                print(f"   Scroll (steps) failed: {e}")
                return False # If scroll itself fails, likely cannot proceed

            for item in target_texts_or_selectors:
                if attempt_click(item): return True
            
    print(f"❌ Could not find or click any of {target_texts_or_selectors} for '{description}' after scrolling.")
    return False

def dump_ui_tree(d):
    print("\n🔍 Dumping visible UI elements:")
    try:
        xml_dump = d.dump_hierarchy(compressed=False) # Corrected: pass device object 'd'
        # Parsing and printing logic (omitted for brevity, same as before)
        for line_num, line in enumerate(xml_dump.splitlines()):
            # (Same UI dump parsing as your previous good version)
            node_info = {}
            try:
                attributes = line.strip().replace(">", "").split(' ') 
                for attr in attributes:
                    if '=' in attr:
                        key_value = attr.split('=', 1)
                        if len(key_value) == 2:
                            node_info[key_value[0]] = key_value[1].strip('"')
            except Exception: pass
            parts = [f"L{line_num}"]
            text = node_info.get('text'); res_id = node_info.get('resource-id'); desc = node_info.get('content-desc')
            clickable = node_info.get('clickable') == 'true'; scrollable = node_info.get('scrollable') == 'true'
            if text and text != "": parts.append(f"text='{text}'")
            if res_id and res_id != "": parts.append(f"id='{res_id}'")
            if desc and desc != "": parts.append(f"desc='{desc}'")
            if clickable: parts.append('[clickable]')
            if scrollable: parts.append('[scrollable]')
            if len(parts) > 1: print(f"  - {' | '.join(parts)}")

    except Exception as e:
        print(f"Failed to dump UI tree: {e}")
    print("--- End of UI Dump ---\n")

def press_home_button(d, step_description=""):
    print(f"   Attempting to press Home button ({step_description})...")
    try:
        # Prioritize specific selectors if known, then generic press
        if d(resourceId="com.android.systemui:id/home", clickable=True).exists(timeout=0.5):
            d(resourceId="com.android.systemui:id/home").click()
            print("   👍 Clicked Home button (by resourceId).")
        elif d(description="Home", clickable=True).exists(timeout=0.5): # Common description
            d(description="Home").click()
            print("   👍 Clicked Home button (by description).")
        else:
            d.press("home")
            print("   👍 Pressed Home button (generic).")
        time.sleep(2.5) # Wait for home screen to settle
        return True
    except Exception as e:
        print(f"   ⚠️ Error pressing Home button ({step_description}): {e}")
        return False

# --- Main Script ---
def main():
    d = u2.connect()
    d.implicitly_wait(5)
    d.settings['operation_delay'] = (0.5, 1) # Small delay between operations

    # --- App and Text Definitions (Customize these!) ---
    APP_DRAWER_SELECTORS = [
        {"descriptionMatches": "(?i)apps"}, {"content-descMatches": "(?i)all apps"}, # Prefer these
        {"textMatches": "(?i)apps"}
    ]
    SETTINGS_APP_TEXTS = ["Settings"] # "Settings"
    APPS_ENTRY_TEXTS = ["Apps"] # "Apps" or "Apps & notifications"
    TARGET_APP_NAME = "タクパト"
    PERMISSIONS_ENTRY_TEXT = "Permissions" # "Permissions"
    PERMISSIONS_TO_SET = [
        {"category": "Camera", "allow_texts": ["許可する", "許可", "常に許可", "アプリの使用中のみ許可"]}, # Camera, Allow texts
        {"category": "位置情報", "allow_texts": ["許可する", "許可", "常に許可", "アプリの使用中のみ許可"]}, # Location
        {"category": "マイク", "allow_texts": ["許可する", "許可", "アプリの使用中のみ許可"]}, # Microphone
        {"category": "電話", "allow_texts": ["許可する", "許可"]}, # Phone
        {"category": "ストレージ", "allow_texts": ["許可する", "許可"]}, # Storage (or Files and media)
        # For newer Android, Storage might be "ファイルとメディア" (Files and media)
        # And location might have "正確な位置情報を使用" (Use precise location) toggle within its own screen.
        # This script assumes a simple click on category -> click "Allow" on next screen.
    ]
    # Define what an "Allow" button looks like for the permission grant dialog
    ALLOW_POPUP_DEFINITION_TEMPLATE = [
        # Order matters: Try more specific "Allow" texts first
        # This will be customized per permission if needed, or use a generic list
        # For now, this template will be used, and `allow_texts` from PERMISSIONS_TO_SET will populate it.
    ]


    MAX_OUTER_ATTEMPTS = 2 # Max attempts to get to TARGET_APP_NAME's App Info screen in Settings
    app_info_reached = False

    print(f"🚀 Starting automation for '{TARGET_APP_NAME}' permissions...")

    for attempt in range(MAX_OUTER_ATTEMPTS):
        print(f"\n▶️ Navigating to '{TARGET_APP_NAME}' App Info: Attempt {attempt + 1}/{MAX_OUTER_ATTEMPTS}")
        
        if not press_home_button(d, f"start of attempt {attempt+1}"):
            print("❌ Failed to press home button. Critical error.")
            dump_ui_tree(d); return

        # 1. Open App Drawer
        print("   🚪 Opening App Drawer...")
        app_drawer_opened = False
        for _try in range(2): # Try twice to open app drawer (direct, then after home)
            for selector in APP_DRAWER_SELECTORS:
                if click_element(d, selector, "App Drawer", timeout=4, post_click_delay=1.0):
                    app_drawer_opened = True; break
            if app_drawer_opened: break
            if _try == 0: # If first try failed, press home and try again
                print("      App Drawer not found directly. Pressing Home and retrying...")
                if not press_home_button(d, "App Drawer retry"): continue # Next outer attempt if home fails
        
        if not app_drawer_opened:
            print(f"   ❌ Failed to open App Drawer in attempt {attempt + 1}.")
            if attempt < MAX_OUTER_ATTEMPTS - 1: continue
            else: print("❌ CRITICAL: Max attempts reached to open App Drawer. Exiting."); dump_ui_tree(d); return

        # 2. Open Android Settings
        print(f"   ⚙️ Opening Android Settings ('{SETTINGS_APP_TEXTS[0]}')...")
        if not scroll_and_click_once(d, SETTINGS_APP_TEXTS, "Settings App", max_scroll_attempts=4, initial_check_timeout=3):
            print(f"   ❌ Failed to open Settings App in attempt {attempt + 1}.")
            if attempt < MAX_OUTER_ATTEMPTS - 1: continue
            else: print("❌ CRITICAL: Max attempts reached to open Settings. Exiting."); dump_ui_tree(d); return
        
        # 3. Inside Android Settings
        print("   🔧 Navigating within Settings...")
        try:
            # Scroll 1 time
            for i in range(1):
                print(f"      Scrolling in Settings: {i+1}/1")
                scrollable = d(scrollable=True)
                if scrollable.exists(timeout=2):
                    scrollable.scroll.vert.forward(steps=50) # Adjust steps as needed
                    time.sleep(1)
                else:
                    print("      No scrollable element for initial scrolls in Settings.")
                    break # No point scrolling more if not scrollable
        except Exception as e:
            print(f"      Error during initial scrolls in Settings: {e}")

        #  Inside Android Settings - Click "Apps"
        print("   🔧 Navigating within Settings to find 'Apps'...")
        if not scroll_and_click_once(d, APPS_ENTRY_TEXTS, "Apps entry", max_scroll_attempts=5, scroll_steps=30, initial_check_timeout=3):
            print(f"   ❌ Failed to click Apps entry in Settings in attempt {attempt + 1}.")
            if attempt < MAX_OUTER_ATTEMPTS - 1: continue
            else: print("❌ CRITICAL: Max attempts reached to find Apps entry. Exiting."); dump_ui_tree(d); return
        
        # Scroll to find TARGET_APP_NAME and click it
        print(f"   ⏬ Scrolling to find up and down '{TARGET_APP_NAME}' in Apps list...")
        if not scroll_and_click_once(d, [TARGET_APP_NAME], f"'{TARGET_APP_NAME}' app in list", max_scroll_attempts=10, scroll_to_end_first=True, initial_check_timeout=1):
            print(f"   ❌ Failed to find and click '{TARGET_APP_NAME}' in Apps list in attempt {attempt + 1}.")
            if attempt < MAX_OUTER_ATTEMPTS - 1: continue
            else: print(f"❌ CRITICAL: Max attempts reached to find '{TARGET_APP_NAME}' in Apps list. Exiting."); dump_ui_tree(d); return

        app_info_reached = True
        print(f"   ✅ Reached '{TARGET_APP_NAME}' App Info screen.")
        break # Exit MAX_OUTER_ATTEMPTS loop

    if not app_info_reached:
        print(f"❌ CRITICAL: Could not navigate to '{TARGET_APP_NAME}' App Info screen after all attempts. Exiting.")
        dump_ui_tree(d); return

    # 4. Inside TARGET_APP_NAME App Info Screen - Click "Permissions"
    print(f"\n   🔐 Clicking '{PERMISSIONS_ENTRY_TEXT}' for '{TARGET_APP_NAME}'...")
    if not click_element(d, {"text": PERMISSIONS_ENTRY_TEXT}, "Permissions entry", timeout=10):
        # Try with textMatches as a fallback
        if not click_element(d, {"textMatches": f"(?i){PERMISSIONS_ENTRY_TEXT}"}, "Permissions entry (regex)", timeout=5):
            print(f"❌ CRITICAL: Failed to click '{PERMISSIONS_ENTRY_TEXT}'. Exiting."); dump_ui_tree(d); return
    
    # 5. Set Permissions
    print(f"\n   🛠️ Setting permissions for '{TARGET_APP_NAME}'...")
    all_permissions_processed_successfully = True
    for perm_info in PERMISSIONS_TO_SET:
        category_name = perm_info["category"]
        allow_button_texts = perm_info["allow_texts"]
        print(f"      ➡️ Processing Permission: {category_name}")

        # Scroll to find and click the permission category (the list itself might be scrollable)
        # Use a selector that is more specific if needed, e.g., if category_name is inside a specific container
        if not scroll_and_click_once(d, [category_name], f"Permission category '{category_name}'", max_scroll_attempts=3, initial_check_timeout=2):
            print(f"      ❌ Could not find or click permission category: {category_name}")
            all_permissions_processed_successfully = False
            # Decide if to continue with other permissions or stop. For now, continue.
            # If the permission screen structure changes, we might need a device.press("back") here
            # but uiautomator2 often handles context shifts.
            # If it gets stuck, check UI dump here.
            if d(text=category_name).exists(): # If still on same screen, implies click failed or no sub-screen
                 print(f"      Still on permission list screen after trying to click {category_name}. Moving to next.")
            else: # Might have gone to a sub-screen but failed to find allow, or something else
                print(f"      Possible navigation issue after trying to click {category_name}. Attempting to go back.")
                d.press("back") # Try to go back to permissions list
                time.sleep(1)
            continue

        # Now, handle the "Allow" / "Deny" screen for this permission
        # Construct the popup definition for allowing this permission
        current_allow_popups = []
        for allow_text in allow_button_texts:
            # Making "Allow" mandatory for this sub-step
            current_allow_popups.append({"textMatches": f"(?i){allow_text}", "type": "allow", "optional": False, "wait": 1.5, "click_timeout": 7})
        # Add a generic "Allow" as a final fallback if specific texts fail
        current_allow_popups.append({"textMatches": "(?i)(許可|ALLOW)", "type": "allow", "optional": False, "wait": 1.5, "click_timeout": 5})


        print(f"         Granting '{category_name}' by clicking one of: {allow_button_texts}")
        if handle_popups_with_retry(d, max_attempts=2, popup_definitions=current_allow_popups):
            print(f"         ✅ Permission '{category_name}' likely granted.")
        else:
            print(f"         ❌ Failed to grant permission '{category_name}'. Check UI if stuck on grant screen.")
            all_permissions_processed_successfully = False
            dump_ui_tree(d) # Dump UI to see the permission grant screen
            # Attempt to go back to the main permissions list if stuck
            print("         Attempting to press 'back' to return to permissions list...")
            d.press("back")
            time.sleep(1)
            # Check if we are back on the permissions list page (e.g. by looking for another permission category)
            if not d(text=PERMISSIONS_TO_SET[-1]["category"]).exists(timeout=2) and \
               not (len(PERMISSIONS_TO_SET) > 1 and d(text=PERMISSIONS_TO_SET[1]["category"]).exists(timeout=2)) :
                 print("         Failed to return to permissions list after attempting back. Critical error.")
                 # This might be a point to exit or retry the entire settings navigation
                 # For now, we'll let it try the next permission category which will likely also fail.

        time.sleep(1) # Wait for UI to settle after granting/denying and potential screen transition

    if not all_permissions_processed_successfully:
        print(f"   ⚠️ Not all permissions for '{TARGET_APP_NAME}' were processed successfully.")
    else:
        print(f"   ✅ All defined permissions for '{TARGET_APP_NAME}' processed.")

    # 6. Return to Home Screen
    print("\n   🏠 Returning to Home Screen...")
    if not press_home_button(d, "after setting permissions"):
        print("   ❌ Failed to return to Home Screen. Script will attempt to continue anyway.")

    # 7. Re-launch TARGET_APP_NAME
    print(f"\n   🚀 Re-launching '{TARGET_APP_NAME}' for final check...")
    final_launch_successful = False
    for final_attempt in range(MAX_OUTER_ATTEMPTS): # Reuse MAX_OUTER_ATTEMPTS or define a new one
        print(f"      Final Launch Attempt {final_attempt + 1}/{MAX_OUTER_ATTEMPTS}")
        if final_attempt > 0: # Press home only on retries
             if not press_home_button(d, f"final launch retry {final_attempt+1}"):
                 print("      ❌ Failed to press home for final launch retry. Critical error.")
                 dump_ui_tree(d); break


        print("         Opening App Drawer for final launch...")
        app_drawer_opened_final = False
        for _try in range(2):
            for selector in APP_DRAWER_SELECTORS:
                if click_element(d, selector, "App Drawer (Final Launch)", timeout=3, post_click_delay=1.0):
                    app_drawer_opened_final = True; break
            if app_drawer_opened_final: break
            if _try == 0 and not press_home_button(d, "App Drawer Final Launch retry"): break

        if not app_drawer_opened_final:
            print("         ❌ Failed to open App Drawer for final launch.")
            if final_attempt < MAX_OUTER_ATTEMPTS -1 : continue
            else: break # Max attempts for final launch

        if scroll_and_click_once(d, [TARGET_APP_NAME], f"'{TARGET_APP_NAME}' app (Final Launch)", max_scroll_attempts=5, initial_check_timeout=3):
            print(f"   🎉 '{TARGET_APP_NAME}' re-launched successfully!")
            final_launch_successful = True
            break
        else:
            print(f"      ❌ Failed to re-launch '{TARGET_APP_NAME}' in attempt {final_attempt + 1}.")
            if final_attempt == MAX_OUTER_ATTEMPTS - 1:
                dump_ui_tree(d)

    if final_launch_successful:
        print("\n✅ Automation task finished successfully.")
    else:
        print(f"\n❌ Automation task finished, but final re-launch of '{TARGET_APP_NAME}' FAILED.")

    # d.press("home") # Optionally go home at the very end
    # d.app_stop_all() # Optionally stop apps

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❗ AN UNEXPECTED SCRIPT ERROR OCCURRED AT THE HIGHEST LEVEL: {str(e)}")
        print("------------------- TRACEBACK -------------------")
        traceback.print_exc()
        print("-------------------------------------------------")
        # Try to get a UI dump if device connection is still alive
        try:
            temp_d = u2.connect() # Try to reconnect if needed
            dump_ui_tree(temp_d)
        except:
            print("Could not get a final UI dump after top-level script error.")