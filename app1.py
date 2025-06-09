import uiautomator2 as u2
import time
import traceback

# --- Helper Functions (UNCHANGED from previous response) ---
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
    
    existence_timeout = max(timeout / 2, 3) 
    if wait_for_element_to_exist(d, selector, timeout=existence_timeout):
        try:
            d(**selector).click() 
            print(f"👍 Clicked (via existence fallback): {description or str(selector)}")
            if post_click_delay > 0: time.sleep(post_click_delay)
            return True
        except Exception as e:
            print(f"❌ Error clicking (via existence fallback) {description or str(selector)}: {str(e)}")
    else:
        print(f"   INFO: Element {selector} not found (for existence check).")
            
    print(f"🚫 Element not successfully clicked: {description or str(selector)}")
    return False

def handle_popups_with_retry(d, max_attempts=3, popup_definitions=None):
    if not popup_definitions:
        print("INFO: No popup definitions provided for handling.")
        return False
    CRITICAL_TYPES = ["confirm", "confirm_alt", "no thanks", "allow"]

    has_mandatory_critical_popup = any(
        p.get("type", "").lower() in CRITICAL_TYPES and not p.get("optional", True)
        for p in popup_definitions
    )
    actioned_mandatory_critical_popup_this_call = False
    any_action_taken_ever = False 

    for attempt in range(max_attempts):
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
            popup_click_timeout = popup_info.get("click_timeout", 5)
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

def scroll_and_click_once(d, target_texts_or_selectors, description="", scroll_steps=30, max_scroll_attempts=3, initial_check_timeout=2, scroll_to_end_first=False, scroll_direction="forward"):
    """
    Scrolls to find and click an element, with added scroll direction control.
    scroll_direction: "forward" (down) or "backward" (up)
    """
    print(f"📜 Scrolling ({scroll_direction}) to find and click: {description or target_texts_or_selectors}")

    def attempt_click(item):
        if isinstance(item, str):
            if click_element(d, {"text": item}, f"{description} (exact: '{item}')", timeout=initial_check_timeout): return True
            if click_element(d, {"textContains": item}, f"{description} (contains: '{item}')", timeout=initial_check_timeout): return True
        elif isinstance(item, dict):
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
                scrollable.fling.toEnd(max_swipes=15)
                time.sleep(1.5)
                for item in target_texts_or_selectors:
                    if attempt_click(item): return True
            else:
                print("   No scrollable view found to scroll to end.")
        except Exception as e:
            print(f"   Error scrolling to end: {e}")

    # Step-by-step scrolling
    for scroll_attempt in range(max_scroll_attempts):
        print(f"   Scrolling step-by-step ({scroll_direction})... (attempt {scroll_attempt + 1}/{max_scroll_attempts})")
        try:
            scrollable = d(scrollable=True)
            if not scrollable.exists(timeout=1):
                print("   No scrollable element found for step scrolling.")
                return False
            
            if scroll_direction == "forward":
                scrollable.scroll.vert.forward(steps=scroll_steps)
            elif scroll_direction == "backward":
                scrollable.scroll.vert.backward(steps=scroll_steps)
            else:
                print(f"Invalid scroll_direction: {scroll_direction}. Must be 'forward' or 'backward'.")
                return False

            time.sleep(1.5)
        except Exception as e: 
            print(f"   Scroll (steps) failed: {e}")
            for item in target_texts_or_selectors:
                if attempt_click(item): return True
            return False 

        for item in target_texts_or_selectors:
            if attempt_click(item): return True
            
    print(f"❌ Could not find or click any of {target_texts_or_selectors} for '{description}' after scrolling.")
    return False

def dump_ui_tree(d):
    print("\n🔍 Dumping visible UI elements:")
    try:
        xml_dump = d.dump_hierarchy(compressed=False)
        for line_num, line in enumerate(xml_dump.splitlines()):
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
            if len(parts) > 1: print(f" - {' | '.join(parts)}")

    except Exception as e:
        print(f"Failed to dump UI tree: {e}")
    print("--- End of UI Dump ---\n")

def press_home_button(d, step_description=""):
    print(f"   Attempting to press Home button ({step_description})...")
    try:
        if d(resourceId="com.android.systemui:id/home", clickable=True).exists(timeout=0.5):
            d(resourceId="com.android.systemui:id/home").click()
            print("   👍 Clicked Home button (by resourceId).")
        elif d(description="Home", clickable=True).exists(timeout=0.5):
            d(description="Home").click()
            print("   👍 Clicked Home button (by description).")
        else:
            d.press("home")
            print("   👍 Pressed Home button (generic).")
        time.sleep(2.5)
        return True
    except Exception as e:
        print(f"   ⚠️ Error pressing Home button ({step_description}): {e}")
        return False

# --- check_and_toggle_permission function (UNCHANGED) ---
def check_and_toggle_permission(d, permission_category_name):
    print(f"\n   Processing permission: '{permission_category_name}'")

    permission_text_label_selector = {"textMatches": f"(?i){permission_category_name}"} 
    if permission_category_name == "Location": 
        permission_text_label_selector = {"textMatches": "(?i)(Location|Location access|Precise location|Location services)"}
    elif permission_category_name == "Storage": 
        permission_text_label_selector = {"textMatches": "(?i)(Storage|Files and media|Photos & videos|Media|Storage usage)"}

    found_permission_element = False
    current_dump_before_scroll = d.dump_hierarchy()
    
    for scroll_attempt in range(5):
        print(f"     Attempting to find and click permission element for '{permission_category_name}' (scroll attempt {scroll_attempt + 1}/5)...")
        
        if click_element(d, permission_text_label_selector, f"Permission category '{permission_category_name}'", timeout=5, post_click_delay=2.0):
            print(f"     ✅ Clicked permission category: '{permission_category_name}'.")
            found_permission_element = True
            break

        scrollable = d(scrollable=True)
        if scrollable.exists(timeout=1):
            scrollable.scroll.vert.forward(steps=30) 
            time.sleep(1.0) 
            if d.dump_hierarchy() == current_dump_before_scroll:
                print("     Reached end of scrollable area or no change. Stopping scroll.")
                break
            current_dump_before_scroll = d.dump_hierarchy()
        else:
            print("     No scrollable element found for permission list to scroll.")
            break

    if not found_permission_element:
        print(f"     ❌ Could not locate and click permission category for: '{permission_category_name}' after all attempts.")
        dump_ui_tree(d) 
        return False

    allow_button_selector = {"textMatches": "(?i)(Allow|While using the app|Only this time|Ask every time)", "clickable": True}
    deny_button_selector = {"textMatches": "(?i)(Deny|Don't allow)", "clickable": True}
    
    time.sleep(1.0) 

    if d(**allow_button_selector).exists(timeout=2):
        print(f"     Detected a permission dialog for '{permission_category_name}'. Attempting to click 'Allow'.")
        if click_element(d, allow_button_selector, "Allow permission", timeout=5):
            print(f"     ✅ Successfully clicked 'Allow' for '{permission_category_name}'.")
            time.sleep(1.0)
            return True
        else:
            print(f"     ❌ Failed to click 'Allow' for '{permission_category_name}'.")
            dump_ui_tree(d)
            return False
    elif d(**deny_button_selector).exists(timeout=2):
        print(f"     Detected a 'Deny' option for '{permission_category_name}', but no 'Allow' option within timeout.")
        print(f"     This suggests the permission might already be granted, or there's no direct 'Allow' button.")
        print(f"     Or it's a 'Don't Allow' screen when the permission is Off, which we cannot automate to 'Allow' directly.")
        dump_ui_tree(d)
        return False
    else:
        print(f"     No 'Allow/Deny' screen or explicit 'Deny' option detected after clicking '{permission_category_name}'.")
        print(f"     Assuming permission was handled by direct click or was already granted/in a stable state.")
        return True

# --- Main Script (MODIFIED for Apps entry selection) ---
def main():
    d = u2.connect()
    d.implicitly_wait(5)
    d.settings['operation_delay'] = (0.5, 1)

    APP_DRAWER_SELECTORS = [
        {"descriptionMatches": "(?i)apps"}, {"content-descMatches": "(?i)all apps"},
        {"textMatches": "(?i)apps"}
    ]
    SETTINGS_APP_TEXTS = ["Settings"]
    APPS_ENTRY_TEXTS = ["Apps", "Apps & notifications", "Application manager"] # Added common alternatives
    TARGET_APP_NAME = "タクパト"
    PERMISSIONS_ENTRY_TEXT = "Permissions"
    PERMISSIONS_TO_SET = [
        "Camera",
        "Location",
        "Microphone",
        "Phone",
        "Storage",
    ]

    MAX_OUTER_ATTEMPTS = 2
    app_info_reached = False

    print(f"🚀 Starting automation for '{TARGET_APP_NAME}' permissions...")

    for attempt in range(MAX_OUTER_ATTEMPTS):
        print(f"\n▶️ Navigating to '{TARGET_APP_NAME}' App Info: Attempt {attempt + 1}/{MAX_OUTER_ATTEMPTS}")
        
        if not press_home_button(d, f"start of attempt {attempt+1}"):
            print("❌ Failed to press home button. Critical error.")
            dump_ui_tree(d); return

        print("   🚪 Opening App Drawer...")
        app_drawer_opened = False
        for _try in range(2):
            for selector in APP_DRAWER_SELECTORS:
                if click_element(d, selector, "App Drawer", timeout=4, post_click_delay=1.0):
                    app_drawer_opened = True; break
            if app_drawer_opened: break
            if _try == 0:
                print("       App Drawer not found directly. Pressing Home and retrying...")
                if not press_home_button(d, "App Drawer retry"): continue
        
        if not app_drawer_opened:
            print(f"   ❌ Failed to open App Drawer in attempt {attempt + 1}.")
            if attempt < MAX_OUTER_ATTEMPTS - 1: continue
            else: print("❌ CRITICAL: Max attempts reached to open App Drawer. Exiting."); dump_ui_tree(d); return

        print(f"   ⚙️ Opening Android Settings ('{SETTINGS_APP_TEXTS[0]}')...")
        if not scroll_and_click_once(d, SETTINGS_APP_TEXTS, "Settings App", max_scroll_attempts=4, initial_check_timeout=3):
            print(f"   ❌ Failed to open Settings App in attempt {attempt + 1}.")
            if attempt < MAX_OUTER_ATTEMPTS - 1: continue
            else: print("❌ CRITICAL: Max attempts reached to open Settings. Exiting."); dump_ui_tree(d); return
        
        # --- REVISED LOGIC FOR APPS ENTRY ---
        apps_entry_clicked = False
        
        print(f"   Attempting to find and click '{APPS_ENTRY_TEXTS[0]}' entry in Settings...")
        # 1. Try clicking directly (no initial scroll)
        if click_element(d, {"textMatches": f"(?i)({'|'.join(APPS_ENTRY_TEXTS)})"}, "Apps entry (direct click)", timeout=5):
            apps_entry_clicked = True
        
        if not apps_entry_clicked:
            # 2. Try scrolling UP a few times
            print("   'Apps' entry not found directly. Trying to scroll UP to find it...")
            if scroll_and_click_once(d, APPS_ENTRY_TEXTS, "Apps entry (scroll up)", max_scroll_attempts=2, scroll_steps=20, scroll_direction="backward"):
                apps_entry_clicked = True
        
        if not apps_entry_clicked:
            # 3. If not found, scroll to top and then scroll DOWN slowly
            print("   'Apps' entry not found scrolling up. Scrolling to top and then searching DOWN...")
            scrollable = d(scrollable=True)
            if scrollable.exists(timeout=1):
                print("   Flinging to top...")
                scrollable.fling.toBeginning(max_swipes=10) # Scroll to top
                time.sleep(2.0)
            
            if scroll_and_click_once(d, APPS_ENTRY_TEXTS, "Apps entry (scroll down)", max_scroll_attempts=5, scroll_steps=20, scroll_direction="forward"):
                apps_entry_clicked = True

        if not apps_entry_clicked:
            print(f"   ❌ Failed to click Apps entry in Settings in attempt {attempt + 1}.")
            if attempt < MAX_OUTER_ATTEMPTS - 1: continue
            else: print("❌ CRITICAL: Max attempts reached to find Apps entry. Exiting."); dump_ui_tree(d); return
        # --- END REVISED LOGIC FOR APPS ENTRY ---
        
        print(f"   ⏬ Scrolling to find '{TARGET_APP_NAME}' in Apps list...")
        if not scroll_and_click_once(d, [TARGET_APP_NAME], f"'{TARGET_APP_NAME}' app in list", max_scroll_attempts=10, scroll_to_end_first=True, initial_check_timeout=1):
            print(f"   ❌ Failed to find and click '{TARGET_APP_NAME}' in Apps list in attempt {attempt + 1}.")
            if attempt < MAX_OUTER_ATTEMPTS - 1: continue
            else: print(f"❌ CRITICAL: Max attempts reached to find '{TARGET_APP_NAME}' in Apps list. Exiting."); dump_ui_tree(d); return

        app_info_reached = True
        print(f"   ✅ Reached '{TARGET_APP_NAME}' App Info screen.")
        break

    if not app_info_reached:
        print(f"❌ CRITICAL: Could not navigate to '{TARGET_APP_NAME}' App Info screen after all attempts. Exiting.")
        dump_ui_tree(d); return

    print(f"\n   🔐 Clicking '{PERMISSIONS_ENTRY_TEXT}' for '{TARGET_APP_NAME}'...")
    if not click_element(d, {"text": PERMISSIONS_ENTRY_TEXT}, "Permissions entry", timeout=10):
        if not click_element(d, {"textMatches": f"(?i){PERMISSIONS_ENTRY_TEXT}"}, "Permissions entry (regex)", timeout=5):
            print(f"❌ CRITICAL: Failed to click '{PERMISSIONS_ENTRY_TEXT}'. Exiting."); dump_ui_tree(d); return
    
    print(f"\n   🛠️ Setting permissions for '{TARGET_APP_NAME}'...")
    all_permissions_processed_successfully = True
    for category in PERMISSIONS_TO_SET:
        if not check_and_toggle_permission(d, category):
            print(f"     ⚠️ Failed or skipped setting permission for '{category}'.")
            all_permissions_processed_successfully = False
        time.sleep(1)

    if not all_permissions_processed_successfully:
        print(f"   ⚠️ Not all permissions for '{TARGET_APP_NAME}' were processed successfully.")
    else:
        print(f"   ✅ All defined permissions for '{TARGET_APP_NAME}' processed.")

    print("\n   🏠 Returning to Home Screen...")
    if not press_home_button(d, "after setting permissions"):
        print("   ❌ Failed to return to Home Screen. Script will attempt to continue anyway.")

    print(f"\n   🚀 Re-launching '{TARGET_APP_NAME}' for final check...")
    final_launch_successful = False
    for final_attempt in range(MAX_OUTER_ATTEMPTS):
        print(f"     Final Launch Attempt {final_attempt + 1}/{MAX_OUTER_ATTEMPTS}")
        if final_attempt > 0:
            if not press_home_button(d, f"final launch retry {final_attempt+1}"):
                print("       ❌ Failed to press home for final launch retry. Critical error.")
                dump_ui_tree(d); break

        print("       Opening App Drawer for final launch...")
        app_drawer_opened_final = False
        for _try in range(2):
            for selector in APP_DRAWER_SELECTORS:
                if click_element(d, selector, "App Drawer (Final Launch)", timeout=3, post_click_delay=1.0):
                    app_drawer_opened_final = True; break
            if app_drawer_opened_final: break
            if _try == 0 and not press_home_button(d, "App Drawer Final Launch retry"): break

        if not app_drawer_opened_final:
            print("       ❌ Failed to open App Drawer for final launch.")
            if final_attempt < MAX_OUTER_ATTEMPTS -1 : continue
            else: break

        if scroll_and_click_once(d, [TARGET_APP_NAME], f"'{TARGET_APP_NAME}' app (Final Launch)", max_scroll_attempts=5, initial_check_timeout=3):
            print(f"   🎉 '{TARGET_APP_NAME}' re-launched successfully!")
            final_launch_successful = True
            break
        else:
            print(f"       ❌ Failed to re-launch '{TARGET_APP_NAME}' in attempt {final_attempt + 1}.")
            if final_attempt == MAX_OUTER_ATTEMPTS - 1:
                dump_ui_tree(d)

    if final_launch_successful:
        print("\n✅ Automation task finished successfully.")
    else:
        print(f"\n❌ Automation task finished, but final re-launch of '{TARGET_APP_NAME}' FAILED.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❗ AN UNEXPECTED SCRIPT ERROR OCCURRED AT THE HIGHEST LEVEL: {str(e)}")
        print("------------------- TRACEBACK -------------------")
        traceback.print_exc()
        print("-------------------------------------------------")
        try:
            temp_d = u2.connect()
            dump_ui_tree(temp_d)
        except:
            print("Could not get a final UI dump after top-level script error.")