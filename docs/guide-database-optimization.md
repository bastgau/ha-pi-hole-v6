# Database optimization

## Exclude sensors from recorder

The following sensors generate **frequent and unnecessary data**. To **reduce database size** and **improve performance**, exclude them from the recorder:

- `sensor.<service_name>_latest_data_refresh`
- `sensor.<service_name>_remaining_until_blocking_mode`

## Slow down the statistics coordinator

The cumulative counters (blocked and total queries, cached, forwarded, unique domains, blocked
domains, FTL diagnosis messages) and the version checks are refreshed by a dedicated coordinator.
Increasing its `Statistics refresh frequency` option (300 seconds by default) reduces the number of
rows they write to the database, without slowing down the blocking status, the switches or the device
trackers. See the [refresh guide](guide-configuring-refresh.md) for the details.

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
