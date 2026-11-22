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

### Verify the Pi-hole certificate

Keep this option enabled so that the integration checks that the server is really your Pi-hole. Pi-hole's default self-signed certificate is not signed by a trusted authority: the integration then shows its SHA-256 fingerprint and asks you to compare it with the one displayed by your Pi-hole before confirming. From then on, only this certificate is trusted.

## Change the address, password or certificate settings

You do not need to delete the service to change how it connects to your Pi-hole. The entities, their history and your automations are kept.

1. On the Pi-hole V6 Integration page (_/config/integrations/integration/pi_hole_v6_), open the menu (⋮) of the service and select **Reconfigure**.
2. Change the address and/or the certificate verification. Enter a new password, or leave the field empty to keep the current one. The name cannot be changed here (you can still rename the service from its menu).
3. Home Assistant tests the connection, then reloads the service.

The connection is always tested. If you changed the address or the certificate verification, or if the certificate presented by the Pi-hole is no longer the one you confirmed, you are asked to compare and confirm its fingerprint again.

> [!NOTE]
> The address and the certificate verification are no longer in the options of the service: they are only available from **Reconfigure**. The options keep the refresh frequencies and the network device tracking.

> [!NOTE]
> If you point the service to another Pi-hole, the same entities are kept and their history continues with the new server. The network devices of the previous Pi-hole are not removed automatically: delete them by hand if you no longer need them.

Enjoy!
