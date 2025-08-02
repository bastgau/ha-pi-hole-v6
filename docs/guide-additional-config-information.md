## Additional configuration information

Here is some additional information if you encounter any problems while adding a new service.

When adding a new service, the following information is requested.

### Name
The name for your Device.

### Address

This is the URL or address of your Pi-Hole's API. All entries should end with `/api`

Exemple: `https://pihole.local:433/api` or `http://192.168.1.2/api`

### Password

This is the password for your Web Admin. If you are using 2FA, you should use Pi-Hole's _app password_ feature.

To enable Pi-Hole's app password, in Pi-Hole's web interface:
1. Go to Settings-> Web Interface/API
2. Select, _configure app password_. (If you do not see the option to configure app password, you may need to enable Expert mode by toggling the Basic button in the upper right part of the screen)
3. In the resulting screen, copy the password in the obfuscated field _before_ proceeding to Step 4
4. Click on '_Enable new app password_'. 

> [!NOTE]
> After completing Step 4, the app password is not recoverable. Be sure to copy it for use in this Integration (and other apps)

Enjoy!
