# Database optimization

## Exclude sensors from recorder

The following sensors generate **frequent and unnecessary data**. To **reduce database size** and **improve performance**, exclude them from the recorder:

- `sensor.<service_name>_latest_data_refresh`
- `sensor.<service_name>_remaining_until_blocking_mode`

## Slow down the inventory coordinator

Network device trackers and inventory sensors (configured clients, DHCP leases, auth sessions, FTL
messages) are refreshed by a dedicated coordinator. Increasing its `Inventory refresh frequency` option
(3600 seconds by default) reduces the number of state changes they write to the database, without
affecting how fast the statistics and the blocking status are refreshed. See the
[refresh guide](guide-configuring-refresh.md) for the details.

## Step-by-Step procedure

1. **Edit your `configuration.yaml`** and add:

```yaml
recorder:
  exclude:
    entities:
      - sensor.<service_name>_latest_data_refresh
      - sensor.<service_name>_remaining_until_blocking_mode
```

2. Restart Home Assistant to apply changes.

3. Verify the sensors no longer appear in the history.

## Need more details?

See the official `recorder` [documentation](https://www.home-assistant.io/integrations/recorder/).
