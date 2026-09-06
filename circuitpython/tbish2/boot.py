import usb_hid
usb_hid.disable()
print("disabling USB HID")

import storage
storage.remount("/", readonly=False, disable_concurrent_write_protection=True)
print("making CIRCUITPY writable, w/ disable_concurrent_write_protection")

# tbish2 saves its knob positions to /tbish2.json when you pause it,
# which needs the filesystem writable from the board's side.
print("boot.py done")
