import uiautomator2 as u2
import time
import traceback

# --- Helper Functions (UNCHANGED) ---

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
    CRITICAL_TYPES = ["confirm", "confirm_alt", "no thanks", "allow", "ok"]

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
    print(f"📜 Scrolling ({scroll_direction}) to find and click: {description or target_texts_or_selectors}")

    def attempt_click(item):
        if isinstance(item, str):
            if click_element(d, {"text": item}, f"{description} (exact: '{item}')", timeout=initial_check_timeout): return True
            if click_element(d, {"textContains": item}, f"{description} (contains: '{item}')", timeout=initial_check_timeout): return True
        elif isinstance(item, dict):
            if click_element(d, item, f"{description} (selector: {item})", timeout=initial_check_timeout): return True
        return False

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
                for attr in attributes: # Corrected: iterate over 'attributes' not 'attr'
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

# --- check_and_toggle_permission function (This is from previous context, not used in VPN script directly) ---
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


# --- Main Automation Function (MODIFIED) ---
def main():
    d = u2.connect()
    d.implicitly_wait(5)
    d.settings['operation_delay'] = (0.5, 1)

    APP_DRAWER_SELECTORS = [
        {"descriptionMatches": "(?i)apps"}, {"content-descMatches": "(?i)all apps"},
        {"textMatches": "(?i)apps"}
    ]
    OPENVPN_APP_NAME = "OpenVPN" # Exact app name in your app drawer
    OVPN_PROFILE_BUTTON_TEXTS = ["OVPN Profile", "Import Profile"] # Common texts for this button
    INTERNAL_STORAGE_TEXTS = ["Internal storage", "Internal Storage", "Files"] # Common texts for internal storage
    DOWNLOAD_FOLDER_TEXTS = ["Download", "Downloads"] # Common texts for download folder
    OVPN_FILE_NAME = "dev900.ovpn" # Exact file name to import
    OVPN_Profiles = "OpenVPN Profile" # Name of the profile after import, used for connection
    IMPORT_BUTTON_TEXTS = ["IMPORT", "Add"] # Common texts for the import button
    ADD_BUTTON_TEXTS = ["Add", "OK"] # Common texts for the add button after import
    OPENVPN_PROFILE_CONNECTION_TEXTS = [OVPN_FILE_NAME] # Text for the profile to connect to (use the file name)
    OK_BUTTON_TEXTS = ["OK", "Yes", "Allow"] # Common texts for confirmation popups including "Allow"

    # New elements for OpenVPN settings
    SIDE_MENU_ICON_SELECTOR = {"descriptionMatches": "(?i)(Open navigation drawer|menu|three lines|side menu)", "className": "android.widget.ImageButton"} # Generic description/class
    SETTINGS_BUTTON_TEXTS = ["Settings"]
    CONTINUOUSLY_RETRY_TEXTS = ["CONTINUOUSLY RETRY", "Retry on connect error"] # Common texts for this setting
    SAVE_BUTTON_TEXTS = ["SAVE", "Save"] # Common texts for save button

    print(f"🚀 Starting OpenVPN profile import and settings automation...")

    # 1. Open App Drawer
    print("   🚪 Opening App Drawer...")
    app_drawer_opened = False
    for _try in range(2):
        for selector in APP_DRAWER_SELECTORS:
            if click_element(d, selector, "App Drawer", timeout=4, post_click_delay=1.0):
                app_drawer_opened = True; break
        if app_drawer_opened: break
        if _try == 0:
            print("       App Drawer not found directly. Pressing Home and retrying...")
            if not press_home_button(d, "App Drawer retry"): 
                print("❌ CRITICAL: Failed to open App Drawer. Exiting."); dump_ui_tree(d); return
    
    if not app_drawer_opened:
        print("❌ CRITICAL: Max attempts reached to open App Drawer. Exiting."); dump_ui_tree(d); return

    # 2. Launch OpenVPN App
    print(f"   🚀 Launching '{OPENVPN_APP_NAME}' app...")
    if not scroll_and_click_once(d, [OPENVPN_APP_NAME], f"'{OPENVPN_APP_NAME}' app in list", max_scroll_attempts=5, initial_check_timeout=3):
        print(f"❌ CRITICAL: Failed to find and launch '{OPENVPN_APP_NAME}'. Exiting."); dump_ui_tree(d); return

    # 3. Click on OVPN Profile button
    print("   📁 Clicking 'OVPN Profile' or 'Import Profile' button...")
    if not click_element(d, {"textMatches": f"(?i)({'|'.join(OVPN_PROFILE_BUTTON_TEXTS)})"}, "OVPN Profile button", timeout=10, post_click_delay=3.0):
        print("❌ CRITICAL: Failed to click 'OVPN Profile' button. Exiting."); dump_ui_tree(d); return

    # 4. Handle "Allow" Popup for Storage/File Access
    print("   🚨 Checking for and handling 'Allow' popup (for storage/file access)...")
    popup_handled = handle_popups_with_retry(d, max_attempts=2, popup_definitions=[
        {"textMatches": "(?i)Allow", "type": "allow", "optional": False, "click_timeout": 5},
        {"textMatches": "(?i)OK", "type": "ok", "optional": True},
        {"textMatches": "(?i)Got it", "type": "info", "optional": True}
    ])
    if not popup_handled:
        print("⚠️ Warning: Did not find or handle 'Allow' popup. Script will attempt to continue.")
        dump_ui_tree(d)

    # 5. Click on Internal Storage (File picker screen)
    print("   🗄️ Clicking 'Internal Storage'...")
    if not click_element(d, {"textMatches": f"(?i)({'|'.join(INTERNAL_STORAGE_TEXTS)})"}, "Internal Storage", timeout=10, post_click_delay=2.0):
        # Fallback for some file managers where 'Internal storage' might not be a direct clickable text.
        # This is a generic approach to find a file path. May need tuning.
        if not click_element(d, {"resourceIdMatches": ".*:id/title|.*:id/root_view", "textMatches": "(?i)Internal storage|Files"}, "Internal Storage (fallback)", timeout=5, post_click_delay=2.0):
            print("❌ CRITICAL: Failed to click 'Internal Storage'. Exiting."); dump_ui_tree(d); return

    # 6. Click on Download folder
    print("   📂 Clicking 'Download' folder...")
    if not scroll_and_click_once(d, DOWNLOAD_FOLDER_TEXTS, "Download folder", max_scroll_attempts=3, initial_check_timeout=3):
        print("❌ CRITICAL: Failed to click 'Download' folder. Exiting."); dump_ui_tree(d); return

    # 7. Click on dev900.ovpn file
    print(f"   📄 Clicking '{OVPN_FILE_NAME}'...")
    if not click_element(d, {"text": OVPN_FILE_NAME}, f"'{OVPN_FILE_NAME}' file", timeout=10, post_click_delay=2.0):
        print(f"❌ CRITICAL: Failed to click '{OVPN_FILE_NAME}'. Exiting."); dump_ui_tree(d); return

    # 8. Click on Import button
    print("   ⬆️ Clicking 'Import' button...")
    if not click_element(d, {"textMatches": f"(?i)({'|'.join(IMPORT_BUTTON_TEXTS)})"}, "Import button", timeout=10, post_click_delay=2.0):
        print("❌ CRITICAL: Failed to click 'Import' button. Exiting."); dump_ui_tree(d); return

    # 9. Click on Add button (after import)
    print("   ➕ Clicking 'Add' button to add profile...")
    if not click_element(d, {"textMatches": f"(?i)({'|'.join(ADD_BUTTON_TEXTS)})"}, "Add button", timeout=10, post_click_delay=3.0):
        print("❌ CRITICAL: Failed to click 'Add' button. Exiting."); dump_ui_tree(d); return
    
    # 10. Click on OpenVPN Profile (to activate/connect)
    # This might be the name of the profile (vpn.databed.org) or a generic "OpenVPN Profile" button.
    print(f"   🔌 Clicking '{OVPN_Profiles}' profile to initiate action (connect/activate)...")
    if not click_element(d, {"text": OVPN_Profiles}, f"'{OVPN_Profiles}' profile", timeout=10, post_click_delay=3.0):
        print(f"       Failed to click '{OVPN_Profiles}' directly. Trying generic connection texts.")
        if not click_element(d, {"textMatches": f"(?i)({'|'.join(OPENVPN_PROFILE_CONNECTION_TEXTS)})"}, "OpenVPN Profile ([dev900])", timeout=10, post_click_delay=3.0):
            print("❌ CRITICAL: Failed to click the VPN profile to connect/activate. Exiting."); dump_ui_tree(d); return

    # 11. Handle "OK" Popup for connection confirmation
    print("   ✅ Checking for and handling 'OK' connection confirmation popup...")
    ok_popup_handled = handle_popups_with_retry(d, max_attempts=2, popup_definitions=[
        {"textMatches": "(?i)OK", "type": "ok", "optional": False, "click_timeout": 5},
        {"textMatches": "(?i)Connect anyway", "type": "ok", "optional": True}, # For untrusted server warnings
        {"textMatches": "(?i)Continue", "type": "ok", "optional": True}
    ])
    if not ok_popup_handled:
        print("⚠️ Warning: Did not find or handle 'OK' confirmation popup. Proceeding to settings.")
        dump_ui_tree(d)

    # --- NEW STEPS START HERE ---

    # 12. Click on the 3-line side menu icon
    print("   ☰ Clicking the side menu icon (3 lines)...")
    menu_icon_clicked = False
    for selector in SIDE_MENU_ICON_SELECTOR:
        if click_element(d, selector, "Side Menu Icon by selector", timeout=5, post_click_delay=2.0):
            menu_icon_clicked = True
            break
     
    if not menu_icon_clicked:
        # Fallback: if side menu is not found by selectors, try clicking near top-left corner
        # Adjust coordinates based on your image and common Android UI.
        # From the image, the icon is left of "OVPN Profiles" text, and the top bar seems to be around 10% of screen height.
        # A tap at (5% of width, 5% of height) should be safe.
        print("       Side menu icon not found by selectors. Trying top-left screen tap as fallback (approx 5% width, 5% height).")
        d.click(d.info['displayWidth'] * 0.05, d.info['displayHeight'] * 0.05) 
        time.sleep(2.0)
        # Verify if the menu opened by checking for "Settings" text (which should now be visible)
        if not d(textMatches=f"(?i)({'|'.join(SETTINGS_BUTTON_TEXTS)})").exists(timeout=2):
            print("❌ CRITICAL: Failed to open side menu. Exiting."); dump_ui_tree(d); return
        menu_icon_clicked = True # Consider it clicked if settings button is now visible
    
    if not menu_icon_clicked: # Final check
        print("❌ CRITICAL: Failed to click side menu icon. Exiting."); dump_ui_tree(d); return


    # 13. Click on Settings button in the side menu
    print("   ⚙️ Clicking 'Settings' button in the side menu...")
    if not click_element(d, {"textMatches": f"(?i)({'|'.join(SETTINGS_BUTTON_TEXTS)})"}, "Settings button", timeout=10, post_click_delay=2.0):
        print("❌ CRITICAL: Failed to click 'Settings' button. Exiting."); dump_ui_tree(d); return

    # 14. Scroll slowly 2 times
    print("   ⬇️ Scrolling down slowly 2 times in Settings...")
    scrollable_settings = d(scrollable=True)
    if not scrollable_settings.exists(timeout=2):
        print("⚠️ Warning: No scrollable element found in Settings. Cannot scroll.")
    else:
        for i in range(2):
            print(f"       Scrolling down (attempt {i+1}/2)...")
            try:
                scrollable_settings.scroll.vert.forward(steps=20) # Slower scroll with fewer steps
                time.sleep(1.5)
            except Exception as e:
                print(f"       Error during scroll {i+1}: {e}")
                break # Stop scrolling if an error occurs

    # 15. Click on "CONTINUOUSLY RETRY" button
    print("   🔄 Clicking 'CONTINUOUSLY RETRY' button...")
    if not scroll_and_click_once(d, CONTINUOUSLY_RETRY_TEXTS, "CONTINUOUSLY RETRY button", max_scroll_attempts=3, scroll_steps=20, initial_check_timeout=3):
        print("❌ CRITICAL: Failed to click 'CONTINUOUSLY RETRY' button. Exiting."); dump_ui_tree(d); return

    # 16. Click on "SAVE" button (top right corner)
    print("   💾 Clicking 'SAVE' button...")
    # This button often appears in the action bar, locate it by resourceId or text + location
    # A common resource ID for a save button in the action bar is 'android:id/action_bar_container' or similar.
    # We can try to find text first, then use coordinates if needed.
    if not click_element(d, {"textMatches": f"(?i)({'|'.join(SAVE_BUTTON_TEXTS)})"}, "SAVE button", timeout=5, post_click_delay=2.0):
        print("       'SAVE' button not found by text. Trying to find it by resourceId or coordinates (top right).")
        # Try a common resourceId for a toolbar/actionbar button
        if not click_element(d, {"resourceIdMatches": ".*:id/save|.*:id/action_save|.*:id/action_done", "clickable": True}, "SAVE button (resourceId)", timeout=3, post_click_delay=2.0):
            # Last resort: click a fixed top-right coordinate (may vary by device)
            print("       'SAVE' button not found by resourceId. Tapping top-right as fallback (approx 90% width, 10% height).")
            d.click(d.info['displayWidth'] * 0.9, d.info['displayHeight'] * 0.1)
            time.sleep(2.0)
            print("⚠️ Warning: Clicked top-right coordinates. This might not be the SAVE button on all devices.")
            # If still not found, we mark as failed
            if not d(textMatches=f"(?i)({'|'.join(SAVE_BUTTON_TEXTS)})").exists(timeout=1): # Recheck if we're back to previous screen or if button is gone
                print("❌ CRITICAL: Failed to confirm 'SAVE' action. Exiting."); dump_ui_tree(d); return
    
    # --- NEW STEPS END HERE ---

    # 17. Go back to Home Screen
    print("   🏠 Returning to Home Screen...")
    if not press_home_button(d, "after OpenVPN settings"):
        print("   ❌ Failed to return to Home Screen. Script finished but manually check home screen.")

    print("\n✅ OpenVPN automation task finished successfully.")

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