"""
Motorola Bootloader Unlocker Script - Python Edition
Port made by Chara/BunnyPad-Dev
Original: https://github.com/eriktim/android-tools/blob/master/scripts/moto-g/unlock-bootloader.sh
"""

import subprocess
import sys
import urllib.parse

def run_command(cmd_string):
    """Robust command runner that pipes execution streams directly."""
    # Split the command string into an executable array (e.g., ['fastboot', 'oem', 'get_unlock_data'])
    cmd_array = cmd_string.split()
    try:
        process = subprocess.Popen(
            cmd_array,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        # Combine both streams since fastboot loves to print data to stderr
        return (stdout + "\n" + stderr).strip()
    except Exception as e:
        return f"Error executing command: {str(e)}"

def main():
    # 1. Check for fastboot devices
    fastboot_check = run_command("fastboot devices")
    if not fastboot_check:
        print("Put your device in fastboot mode (i.e. power off, and then")
        print("press the power and volume down buttons simultaneously).")
        sys.exit(1)

    # 2. Get unlock data
    unlock_data = run_command("fastboot oem get_unlock_data")
    
    # Debug: If you need to see raw output, uncomment the next line
    print(f"DEBUG RAW OUTPUT:\n{unlock_data}\n")

    # 3. Parse the lines cleanly
    hex_lines = []
    for line in unlock_data.splitlines():
        # Remove '(bootloader)' tag if present
        cleaned_line = line.replace("(bootloader)", "").strip()
        
        # Explicitly skip empty lines, headers, or fastboot execution summaries
        if not cleaned_line:
            continue
        if "Unlock data" in cleaned_line or "OKAY" in cleaned_line or "Finished" in cleaned_line:
            continue
            
        hex_lines.append(cleaned_line)

    # Join the pieces into one continuous string, removing remaining spaces/dots
    unlock_key = "".join(hex_lines).replace(".", "").replace(" ", "")

    # Debug: Let's see what the final combined key looks like
    print(f"DEBUG CLEANED KEY: {unlock_key}")

    if not unlock_key or "#" not in unlock_key:
        print("Failed to parse valid unlock data. Is this a Motorola device?")
        sys.exit(1)

    # 4. Parse out the Motorola specific tokens from the string token hash
    tokens = unlock_key.split('#')
    try:
        phone_sn = tokens[0]
        phone_puid = tokens[3]
        phone_hash = tokens[2]
    except IndexError:
        print("Unlock key format was invalid or unexpected.")
        sys.exit(1)

    # 5. Construct the registration URL securely
    base_url = "https://motorola-global-portal.custhelp.com/cc/productRegistration/unlockPhone/"
    url = f"{base_url}{urllib.parse.quote(phone_sn)}/{urllib.parse.quote(phone_puid)}/{urllib.parse.quote(phone_hash)}/"

    print("First log in at the Motorola website if you have not already:\n")
    print("  https://motorola-global-portal.custhelp.com/app/standalone/bootloader/unlock-your-device-a\n")
    print(f"Now visit:\n\n  {url}\n")
    print(f"Or use the unlock key: {unlock_key}\n")

    # 6. Reboot bootloader
    run_command("fastboot reboot-bootloader")

    # 7. Prompt user for the code
    print("")
    unlock_code = input("Enter the unlock code: ").strip()
    print(f"\nAbout to run\n\n  $ fastboot oem unlock {unlock_code}\n")
    
    confirm = input("Do you wish to continue? (y/n) ").strip().lower()
    if confirm != 'y':
        print("Aborted")
        sys.exit(1)

    # 8. Final fastboot safety check
    fastboot_check = run_command("fastboot devices")
    if not fastboot_check:
        print("Your device is not in fastboot mode")
        sys.exit(1)

    print("Wait for your device to fully reboot\n")
    
    # 9. Fire the unlock command
    run_command(f"fastboot oem unlock {unlock_code}")

if __name__ == "__main__":
    main()