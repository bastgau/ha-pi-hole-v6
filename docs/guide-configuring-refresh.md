## How do I configure the refresh frequency?

### Configure the service (recommanded solution)

On the Pi-hole V6 Integration page (_/config/integrations/integration/pi_hole_v6_), configure your service.

<img src="../img/integration-page.png" width="500">

In the pop-up window, enter the desired `Data refresh rate` value in seconds.

<img src="../img/integration-configuration.png" width="500">

### The two refresh frequencies

The integration uses two independent update coordinators, so the data that must feel responsive is not
refreshed at the same pace as the data that only changes slowly. Each one has its own option:

| Option | Default | Entities refreshed | Pi-hole endpoints |
| --- | --- | --- | --- |
| `Data refresh frequency` | 120 s | `binary_sensor.<service>_status`, the main switch, the group switches, `remaining_until_blocking_mode`, `cpu_use`, `memory_use`, `latest_data_refresh` and the four `update` entities | `blocking_status`, `groups`, `padd` |
| `Detailed data refresh frequency` | 300 s | All the statistics sensors (`ads_blocked_today`, `ads_percentage_blocked_today`, `seen_clients`, `dns_queries_today`, `dns_queries_cached`, `dns_queries_forwarded`, `dns_queries_frequency`, `dns_unique_clients`, `dns_unique_domains`, `domains_blocked`), `configured_clients`, `dhcp_leases`, `auth_sessions`, `ftl_info_message_count` and every `device_tracker` entity | `summary`, `clients`, `dhcp/leases`, `auth/sessions`, `info/messages`, `network/devices` |

The detailed frequency must be greater than or equal to the data refresh frequency. Raising it is the
recommended way to stop the statistics sensors and the network device trackers from filling the recorder
database, while the blocking status and the switches keep reacting quickly.

Pressing the `Refresh data` button refreshes both coordinators at once.

### Deactivate the default refresh (alternative solution)

In the integration page, you have to deactivate the automatic polling for the `Pi-hole V6` Integration.

#### 1. Open the system options

Click on the `System options` to open the options.

<img src="../img/manual-refresh-01.png" width="300">

#### 2. Deactivate the automatic polling

Uncheck the option `Enable polling for changes` to deactivate the automatic polling.

<img src="../img/manual-refresh-02.png" width="300">

### Create an Automation

#### 1. Access Settings

Open your Home Assistant interface. Click on the `Settings` icon.

#### 2. Navigate to Automations & Scenes
   
In the settings menu, select `Automations & Scenes`.

#### 3. Create a New Automation

Click on `Create automation` to start a new automation.  
Select `Create new automation` to begin the creation process.

#### 4. Access the YAML Editor

Once in the new automation, click on the `three dots` on the right side of the screen.

Select `Edit in YAML` to open the YAML editor.

#### 5. Write the YAML Code

In the YAML editor, you can now write the code to configure the refresh of your integration. Here is a basic example:

```yaml
alias: Force Pi-hole Refresh
description: "Refresh Pi-hole every minute"
triggers:
  - trigger: time_pattern
    minutes: /1
    hours: "*"
conditions: []
actions:
  - action: homeassistant.update_entity
    metadata: {}
    data:
      entity_id:
        - binary_sensor.pi_hole_status
mode: single
```

You can define the wanted frequency.

#### 6. Save and Test

After writing the code, `save` the automation then test the automation to ensure it works as expected.
