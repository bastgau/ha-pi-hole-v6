# Database optimization

## Exclude sensors from recorder

The following sensors generate **frequent and unnecessary data**. To **reduce database size** and **improve performance**, exclude them from the recorder:

- `sensor.<service_name>_latest_data_refresh`
- `sensor.<service_name>_remaining_until_blocking_mode`

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

See the official `Recorder` [documentation](https://www.home-assistant.io/integrations/recorder/).
