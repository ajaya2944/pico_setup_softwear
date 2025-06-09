# Import required libraries
import uiautomator2 as u2  # For Android UI automation
import time  # For delays and timeouts
import traceback  # For detailed error logging

# Connect to device using uiautomator2
device = u2.connect()
device.implicitly_wait(5)  # Set global implicit wait for element finding to 5 seconds

# --- START OF HELPER FUNCTIONS (UNCHANGED FROM PREVIOUS GOOD VERSION) ---

def wait_for_element_to_exist(selector, timeout=5, interval=0.3):
    """
    Wait only for an element matching the selector to exist.
    Args:
        selector: Dictionary of UI element attributes to match
        timeout: Maximum time to wait in seconds
        interval: Time between checks
    Returns:
        bool: True if element exists, False if timeout reached
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            if device(**selector).exists:
                return True
        except u2.exceptions.UiObjectNotFoundError:
            pass
        except Exception as e:
            print(f"⚠️ Error checking existence for {selector}: {str(e)}")
        time.sleep(interval)
    return False

def wait_for_element_clickable(selector, timeout=10, interval=0.5):
    """
    Wait for element to become clickable AND exist.
    Args:
        selector: Dictionary of UI element attributes to match
        timeout: Maximum time to wait in seconds
        interval: Time between checks
    Returns:
        bool: True if element is clickable, False if timeout reached
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            element = device(**selector)
            if element.exists and element.info.get('clickable', False):
                return True
        except u2.exceptions.UiObjectNotFoundError:
            pass
        except Exception as e:
            print(f"⚠️ Error checking clickability for {selector}: {str(e)}")
        time.sleep(interval)
    return False

def click_element(selector, description="", timeout=10, post_click_delay=1.5):
    """
    Find and click an element with robust fallback logic.
    Args:
        selector: Dictionary of UI element attributes to match
        description: Human-readable description for logging
        timeout: Maximum time to wait for element
        post_click_delay: Time to wait after clicking
    Returns:
        bool: True if click succeeded, False otherwise
    """
    print(f"Attempting to click: {description or str(selector)}")

    # First try to find directly clickable element
    if wait_for_element_clickable(selector, timeout=timeout):
        try:
            device(**selector).click()
            print(f"👍 Clicked (directly clickable match): {description or str(selector)}")
            if post_click_delay > 0: time.sleep(post_click_delay)
            return True
        except Exception as e:
            print(f"❌ Error clicking (even though found clickable) {description or str(selector)}: {str(e)}")
    
    # Fallback: Try existence check + parent click heuristic
    if 'clickable' not in selector or not selector.get('clickable'):
        print(f"   INFO: Direct clickable match failed for {selector}. Trying existence + parent heuristic...")
        existence_timeout = max(timeout / 2, 3) 
        if wait_for_element_to_exist(selector, timeout=existence_timeout):
            try:
                device(**selector).click() 
                print(f"👍 Clicked (via existence + parent heuristic): {description or str(selector)}")
                if post_click_delay > 0: time.sleep(post_click_delay)
                return True
            except Exception as e:
                print(f"❌ Error clicking (via existence + parent heuristic) {description or str(selector)}: {str(e)}")
        else:
            print(f"   INFO: Element {selector} not found (for existence check).")
            
    print(f"🚫 Element not successfully clicked: {description or str(selector)}")
    return False

def handle_popups_with_retry(max_attempts=2, popup_definitions=None):
    """
    Handle a sequence of potential popups with retry logic.
    Args:
        max_attempts: Maximum number of attempts to handle popups
        popup_definitions: List of popup definitions to handle
    Returns:
        bool: True if all mandatory popups were handled, False otherwise
    """
    if not popup_definitions:
        print("INFO: No popup definitions provided for handling.")
        return False

    # Define which popup types are considered critical
    CRITICAL_TYPES = ["confirm", "confirm_alt", "no thanks"] 

    # Check if there are any mandatory critical popups in definitions
    has_mandatory_critical_popup = any(
        p.get("type", "").lower() in CRITICAL_TYPES and not p.get("optional", True)
        for p in popup_definitions
    )
    actioned_mandatory_critical_popup_this_call = False
    any_action_taken_ever = False 

    # Main retry loop
    for attempt in range(max_attempts):
        # Create log-friendly names for popups
        popup_names_for_log = []
        for p_info in popup_definitions:
            if "textMatches" in p_info: popup_names_for_log.append(f"'{p_info['textMatches']}' (regex)")
            elif "text" in p_info: popup_names_for_log.append(f"'{p_info['text']}'")
            elif "resourceId" in p_info: popup_names_for_log.append(f"id='{p_info['resourceId']}'")
            else: popup_names_for_log.append("UnknownSelector")
        print(f"Popup handling attempt {attempt + 1}/{max_attempts} for priority list: {', '.join(popup_names_for_log)}")
        
        action_taken_this_attempt = False

        # Try each popup in the defined sequence
        for popup_info in popup_definitions: 
            selector = {}
            selector_desc = "Unknown"

            # Build selector based on available attributes
            if "textMatches" in popup_info:
                selector = {"textMatches": popup_info["textMatches"]}
                selector_desc = f"textMatches='{popup_info['textMatches']}'"
            elif "text" in popup_info:
                selector = {"text": popup_info["text"]}
                selector_desc = f"text='{popup_info['text']}'"
            elif "resourceId" in popup_info: 
                selector = {"resourceId": popup_info["resourceId"]}
                selector_desc = f"resourceId='{popup_info['resourceId']}'"
            else:
                print(f"   ⚠️ Skipping popup_info due to missing selector key: {popup_info}")
                continue
            
            # Get popup handling parameters
            popup_type_from_def = popup_info.get("type", "info")
            popup_type_internal = popup_type_from_def.lower() 
            popup_wait = popup_info.get("wait", 1.0)
            popup_click_timeout = popup_info.get("click_timeout", 7) 
            is_optional_popup = popup_info.get("optional", True) 
            
            # Try to handle this popup
            if click_element(selector, f"Popup '{selector_desc}' (Type: {popup_type_from_def}, Optional: {is_optional_popup})", timeout=popup_click_timeout, post_click_delay=popup_wait):
                print(f"   ✅ Actioned: {selector_desc}")
                any_action_taken_ever = True
                action_taken_this_attempt = True 
                
                # Check if this was a critical popup
                if popup_type_internal in CRITICAL_TYPES: 
                    print(f"   🎉 Critical type popup '{selector_desc}' (type: {popup_type_from_def}) handled.")
                    if not is_optional_popup: 
                        actioned_mandatory_critical_popup_this_call = True
                    return True 
                
                break 
            else:
                pass 
        
        # Evaluate attempt results
        if action_taken_this_attempt: 
            if not has_mandatory_critical_popup:
                print(f"   Action taken (non-critical) in attempt {attempt + 1}, and no mandatory critical types were defined. Handler successful.")
                return True
            else:
                print(f"   Non-critical action taken in attempt {attempt + 1}. Mandatory critical type is defined. Will proceed to next attempt if available.")
        
        if not action_taken_this_attempt and attempt < max_attempts - 1:
            print(f"   No popups from the list were actioned in attempt {attempt + 1}. Retrying list...")
            time.sleep(1) 
    
    # Final evaluation after all attempts
    if actioned_mandatory_critical_popup_this_call: 
        print(f"✅ Popup handling SUCCEEDED: A mandatory critical popup was actioned.")
        return True
    if has_mandatory_critical_popup and not any_action_taken_ever:
        print(f"❌ Popup handling FAILED: A mandatory critical type popup was defined, but NO popup from the list was actioned after {max_attempts} attempts.")
        return False
    if has_mandatory_critical_popup and any_action_taken_ever and not actioned_mandatory_critical_popup_this_call:
        print(f"❌ Popup handling FAILED: Actions were taken on some popups, but a defined MANDATORY critical popup was not actioned after {max_attempts} attempts.")
        return False
    if any_action_taken_ever: 
        print(f"✅ Popup handling SUCCEEDED: Actions were taken (on optional critical/info popups as no mandatory critical ones were defined or missed).")
        return True
    else: 
        print(f"INFO: Popup handling: No popups from the defined sequence were actioned after all attempts.")
        return False

def scroll_and_click_once(target_texts, description="", scroll_steps=30, max_scroll_attempts=3, initial_check_timeout=2):
    """
    Scroll to find and click an element matching target text(s).
    Args:
        target_texts: List of text patterns to search for
        description: Human-readable description for logging
        scroll_steps: Number of scroll steps per attempt
        max_scroll_attempts: Maximum scroll attempts
        initial_check_timeout: Timeout for initial element check
    Returns:
        bool: True if element was found and clicked, False otherwise
    """
    print(f"📜 Scrolling to find and click: {description or target_texts}")

    # First check if element is already visible without scrolling
    for text_pattern in target_texts:
        if click_element({"text": text_pattern}, f"{description} (initial check, exact: '{text_pattern}')", timeout=initial_check_timeout, post_click_delay=1.0):
            return True
        if click_element({"textContains": text_pattern}, f"{description} (initial check, contains: '{text_pattern}')", timeout=initial_check_timeout, post_click_delay=1.0):
            return True

    # Scroll and search loop
    for scroll_attempt in range(max_scroll_attempts):
        print(f"   Scrolling... (attempt {scroll_attempt + 1}/{max_scroll_attempts})")
        try:
            # Find scrollable view and scroll forward
            scrollable_view = device(scrollable=True)
            if not scrollable_view.exists(timeout=1): 
                print("   No scrollable element found. Cannot scroll this view.")
                # Final check without scrolling
                for text_pattern_no_scroll in target_texts: 
                    if click_element({"text": text_pattern_no_scroll}, f"{description} (final check, no scrollable: '{text_pattern_no_scroll}')", timeout=1, post_click_delay=0.5): return True
                    if click_element({"textContains": text_pattern_no_scroll}, f"{description} (final check, no scrollable, contains: '{text_pattern_no_scroll}')", timeout=1, post_click_delay=0.5): return True
                return False
            scrollable_view.scroll.vert.forward(steps=scroll_steps)
            time.sleep(1.5) 
        except Exception as e: 
            print(f"   Scroll failed: {e}")
            # Final check after scroll failure
            for text_pattern_after_fail in target_texts: 
                if click_element({"text": text_pattern_after_fail}, f"{description} (final check, after scroll fail: '{text_pattern_after_fail}')", timeout=1, post_click_delay=0.5): return True
                if click_element({"textContains": text_pattern_after_fail}, f"{description} (final check, after scroll fail, contains: '{text_pattern_after_fail}')", timeout=1, post_click_delay=0.5): return True
            return False

        # Check for elements after successful scroll
        for text_pattern in target_texts:
            if click_element({"text": text_pattern}, f"{description} (post-scroll, exact: '{text_pattern}')", timeout=2, post_click_delay=1.0):
                return True
            if click_element({"textContains": text_pattern}, f"{description} (post-scroll, contains: '{text_pattern}')", timeout=2, post_click_delay=1.0):
                return True
            
    print(f"❌ Could not find or click any of {target_texts} for '{description}' after scrolling.")
    return False

def dump_ui_tree():
    """
    Dump visible UI elements for debugging purposes.
    """
    print("\n🔍 Dumping visible UI elements:")
    try:
        xml_dump = device.dump_hierarchy(compressed=False)
        for line_num, line in enumerate(xml_dump.splitlines()):
            node_info = {}
            try:
                attributes = line.strip().replace(">", "").split(' ') 
                for attr in attributes:
                    if '=' in attr:
                        key_value = attr.split('=', 1)
                        if len(key_value) == 2:
                            node_info[key_value[0]] = key_value[1].strip('"')
            except Exception:
                pass

            # Build readable node description
            parts = [f"L{line_num}"]
            text = node_info.get('text')
            res_id = node_info.get('resource-id')
            desc = node_info.get('content-desc')
            clickable = node_info.get('clickable') == 'true'
            scrollable = node_info.get('scrollable') == 'true'

            if text and text != "": parts.append(f"text='{text}'")
            if res_id and res_id != "": parts.append(f"id='{res_id}'")
            if desc and desc != "": parts.append(f"desc='{desc}'")
            if clickable: parts.append('[clickable]')
            if scrollable: parts.append('[scrollable]')
            
            if len(parts) > 1: 
                 print(f"  - {' | '.join(parts)}")
    except Exception as e:
        print(f"Failed to dump UI tree: {e}")
    print("--- End of UI Dump ---\n")

def press_home_button(step_description=""):
    """
    Presses the home button using various methods.
    Args:
        step_description: Context description for logging
    Returns:
        bool: True if home button was pressed successfully
    """
    print(f"   Attempting to press Home button ({step_description})...")
    home_pressed_successfully = False
    try:
        # Try different methods to press home button
        if device(resourceId="com.android.systemui:id/home", clickable=True).exists(timeout=0.5):
            device(resourceId="com.android.systemui:id/home").click()
            print("   👍 Clicked Home button (by resourceId).")
            home_pressed_successfully = True
        elif device(description="Home", clickable=True).exists(timeout=0.5):
            device(description="Home").click()
            print("   👍 Clicked Home button (by description).")
            home_pressed_successfully = True
        else:
            print("   INFO: Specific Home button selectors not found, trying generic device.press('home').")
            device.press("home")
            print("   👍 Pressed Home button (generic).")
            home_pressed_successfully = True
        
        if home_pressed_successfully:
            time.sleep(2.5) # Wait for home screen to settle
        return home_pressed_successfully
    except Exception as e:
        print(f"   ⚠️ Error pressing Home button ({step_description}): {e}")
        return False
# --- END OF HELPER FUNCTIONS ---

# ------------------------ MAIN SCRIPT ------------------------
def main():
    """
    Main automation script for configuring SuperSU app.
    """
    try:
        print("🚀 Starting SuperSU automation...")
        time.sleep(1)

        # --- MODIFIED SECTION: Outer loop for App Drawer and SuperSU Launch ---
        max_launch_attempts = 2 # Try to get to SuperSU main screen twice
        supersu_launched_successfully = False

        for launch_attempt in range(max_launch_attempts):
            print(f"\n▶️ App Launch Attempt {launch_attempt + 1}/{max_launch_attempts}")
            
            # 1. App Drawer Opening
            print("   🚪 Attempting to open App Drawer...")
            app_drawer_opened = False
            app_drawer_selectors = [
                {"description": "Apps"}, {"content-desc": "Apps"}, 
                {"descriptionMatches": "(?i)apps"}, {"content-descMatches": "(?i)all apps"},
                {"text": "Apps"}, {"textMatches": "(?i)apps"}
            ]

            # Try 1.1: Open App Drawer directly
            for selector in app_drawer_selectors:
                if click_element(selector, "App Drawer (Direct Attempt)", timeout=3, post_click_delay=1.0):
                    app_drawer_opened = True
                    break
            
            # Try 1.2: Press home and retry if direct attempt failed
            if not app_drawer_opened:
                print("      App Drawer not found directly. Pressing Home and retrying...")
                if press_home_button("during App Drawer"):
                    print("      Retrying App Drawer...")
                    for selector in app_drawer_selectors:
                        if click_element(selector, "App Drawer (After Home Press)", timeout=5):
                            app_drawer_opened = True
                            break
            
            # Handle failure to open app drawer
            if not app_drawer_opened:
                print(f"   ❌ Failed to open App Drawer in launch attempt {launch_attempt + 1}.")
                if launch_attempt < max_launch_attempts - 1:
                    print(f"      Will return to Home and try entire launch sequence again.")
                    press_home_button("before next launch attempt")
                    continue
                else:
                    print("❌ CRITICAL: Max attempts reached to open App Drawer. Exiting.")
                    dump_ui_tree()
                    return
            
            print("   ✅ App Drawer opened successfully.")

            # 2. Launch SuperSU from App Drawer
            print("   📱 Attempting to launch SuperSU from App Drawer...")
            if scroll_and_click_once(
                target_texts=["SuperSU", "Super"], 
                description="SuperSU App", 
                max_scroll_attempts=5, 
                initial_check_timeout=3
            ):
                print("   ✅ SuperSU Launched successfully from App Drawer.")
                supersu_launched_successfully = True
                break
            else:
                print(f"   ❌ Failed to launch SuperSU from App Drawer in launch attempt {launch_attempt + 1}.")
                if launch_attempt < max_launch_attempts - 1:
                    print(f"      Will return to Home and try entire launch sequence again.")
                    press_home_button("before next launch attempt")
                else:
                    print("❌ CRITICAL: Max attempts reached to launch SuperSU. Exiting.")
                    dump_ui_tree()
                    return
        
        # Final check if SuperSU was launched
        if not supersu_launched_successfully:
            print("❌ CRITICAL: SuperSU could not be launched after all attempts. Exiting.")
            return

        time.sleep(2) # Wait for SuperSU to load after successful launch

        # 3. Handle initial SuperSU popups
        print("\n🔄 Handling initial SuperSU popups...")
        initial_popups = [
            {"text": "Start", "wait": 2.0, "type": "info", "optional": True},
            {"textMatches": "(?i)CANCEL", "wait": 1.5, "type": "cancel", "optional": True},
            {"textMatches": "(?i)OK", "wait": 2.0, "type": "confirm", "optional": False}, 
            {"textMatches": "(?i)NO THANKS", "wait": 2.0, "type": "no thanks", "optional": True, "click_timeout": 10}
        ]
        
        if handle_popups_with_retry(max_attempts=2, popup_definitions=initial_popups):
            print("✅ Initial SuperSU popups processed.")
        else:
            print("⚠️ Initial SuperSU popups FAILED (a mandatory action might have been missed). Check UI.")
            dump_ui_tree()
        
        time.sleep(1) 

        # Handle the "Follow me" / "NO THANKS" popup
        print("\n🔄 Handling 'Follow me' social media popup (if present)...")
        follow_me_popups = [
             {"text": "Start", "wait": 2.0, "type": "info", "optional": True},
             {"textMatches": "(?i)CANCEL", "wait": 1.5, "type": "cancel", "optional": True},
             {"textMatches": "(?i)OK", "wait": 2.0, "type": "confirm", "optional": False},
             {"textMatches": "(?i)NO THANKS", "wait": 2.0, "type": "no thanks", "optional": True, "click_timeout": 10}
        ]

        if handle_popups_with_retry(max_attempts=2, popup_definitions=follow_me_popups):
            print("✅ 'Follow me' popup handled.")
        else:
            print("INFO: 'Follow me' popup was not present or not actioned as defined. Proceeding.")
        time.sleep(1) 

        # 4. Click "SETTINGS" tab/button
        print("\n⚙️ Navigating to SuperSU SETTINGS...")
        settings_clicked = click_element(
            {"textMatches": "(?i)SETTINGS"}, 
            "SETTINGS tab", 
            timeout=7, 
            post_click_delay=2.5
        )
        
        if settings_clicked:
            print("✅ Clicked 'SETTINGS' tab.")
            
            # Scroll within settings
            print("\n📜 Scrolling once inside SETTINGS screen...")
            try:
                scrollable_view_settings = device(scrollable=True) 
                if scrollable_view_settings.exists(timeout=2): 
                    scrollable_view_settings.scroll.vert.forward(steps=40) 
                    time.sleep(1.5) 
                    print("   Scrolled within SETTINGS.")
                else:
                    print("   No scrollable element found to scroll inside SETTINGS tab (might be okay if content is short).")
            except Exception as e:
                print(f"   Scroll inside SETTINGS failed: {e}")

            # Configure Default access
            print("\n⚙️ Configuring Default access...")
            default_access_texts = ["Default access", "Default"]
            if scroll_and_click_once(default_access_texts, description="Default access setting", max_scroll_attempts=2, initial_check_timeout=3):
                print("✅ Clicked 'Default access'.")
                time.sleep(1.5) 

                # Set Default access to Grant
                print("\n🛡️ Setting Default access to Grant...")
                grant_popup_def = [
                    {"textMatches": "(?i)Grant", "wait": 2.0, "type": "confirm", "optional": False},
                    {"textMatches": "(?i)CANCEL", "wait": 1.0, "type": "cancel", "optional": True} 
                ]
                if handle_popups_with_retry(max_attempts=2, popup_definitions=grant_popup_def):
                    print("✅ 'Grant' selected for Default access.")
                    time.sleep(2)

                    # Configure notifications
                    print("\n🔔 Configuring Show notifications...")
                    notification_options = ["Show notifications", "Notifications", "Notification"]
                    if scroll_and_click_once(notification_options, description="Show notifications setting", max_scroll_attempts=2, initial_check_timeout=2):
                        print("✅ 'Show notifications' setting likely actioned (toggled).")
                    else:
                        print("❌ 'Show notifications' option not found or couldn't be clicked after granting default access.")
                        dump_ui_tree()
                else:
                    print("❌ Failed to set Default access to 'Grant'. The 'Grant' popup/option was not handled.")
                    dump_ui_tree()
            else:
                print("❌ 'Default access' setting not found after attempting to scroll in SETTINGS.")
                dump_ui_tree()
        else:
            print("❌ 'SETTINGS' tab not clicked. Cannot proceed with SuperSU configuration.")
            dump_ui_tree() 

        # Return to home screen
        print("\n🏠 Returning to Home Screen...")
        press_home_button("at the end of script")

        print("\n🎉 Script finished successfully.")

    except Exception as e:
        # Handle unexpected errors
        print(f"❗ AN UNEXPECTED SCRIPT ERROR OCCURRED: {str(e)}")
        print("------------------- TRACEBACK -------------------")
        traceback.print_exc()
        print("-------------------------------------------------")
        print("Attempting to dump UI tree due to script error...")
        dump_ui_tree()

if __name__ == "__main__":
    main()