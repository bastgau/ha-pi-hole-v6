# A Pi-hole Control Card

A quick card to add in your dashboard in order to control your Pi-hole.

## Prerequisites

In this example, you have to consider that there are two switches.

The first switch is the global switch to deactivate the ads blocking for all devices.

- **name:** Pi-hole
- **entity_id:** switch.pi_hole

The second switch is a group switch to deactivate the ads blocking for all my macbooks.

- **name:** [single] Macbook Air Bastien
- **entity_id:** switch.pi_hole_group_single_macbook_air_bastien

You also need two dropdowns and a script before creating your card in the dashboard.

### Dropdown deactivating delays

In a first time, we create a dropdown with the deactivating delays.

<img src="../img/dropdown-time.png" width="300">

The dropdown entity name is: `input_select.pi_hole_entity_dropdown`.

### Dropdown entity names

In a second time, we create a dropdown with the Pi-hole switches to deactivate.

<img src="../img/dropdown-entity.png" width="300">

The dropdown entity name is: `input_select.pi_hole_entity_dropdown`.

### A script to execute the service to disable the blocking

The script entity_id is: `script.pi_hole_switch_status_off_generic`

```yaml
sequence:
  - variables:
      duration: >
        {{ states.input_select.pi_hole_time_droptdown.state | int |
        timestamp_custom('%H:%M:%S', False) }}
      pihole_entity: >
        {{ states.switch | selectattr('attributes.friendly_name', 'eq',
        states.input_select.pi_hole_entity_dropdown.state | string) |
        map(attribute='entity_id') | list | first }}
  - action: pi_hole_v6.disable
    target:
      entity_id:
        - "{{ pihole_entity }}"
    data:
      duration: "{{ duration }}"
alias: Pi-hole - Switch status OFF (generic)
icon: mdi:pi-hole
mode: single
description: ""
```

## Pi-hole Control Card creation

Now, we will combine the dropbdowns and an entities card.

The Pi-hole control is composed of two parts. A first part to deactivate a blocking after selecting a group.

<img src="../img/pi-hole-control-part-01.png" width="300">

A second part which will be displayed only if the ads blocking is deactivated.

<img src="../img/pi-hole-control-part-02.png" width="300">

The information related to the end of blocking deactivation is diplayed.

The code is available bellow:

```yaml
type: vertical-stack
cards:
  - type: entities
    entities:
      - entity: input_select.pi_hole_entity_dropdown
        name: Pi-hole entity
      - entity: input_select.pi_hole_time_droptdown
        name: Disable time (in seconds)
      - entity: script.pi_hole_switch_status_off_generic
        name: " "
        icon: " "
        action_name: SUSPENDRE
  - type: conditional
    conditions:
      - condition: state
        entity: switch.pi_hole
        state: "off"
    card:
      type: entities
      entities:
        - entity: switch.pi_hole
        - type: attribute
          entity: switch.pi_hole
          attribute: remaining_seconds
          name: Remaining seconds
          icon: mdi:clock
        - type: attribute
          entity: switch.pi_hole
          attribute: until_date
          name: Disabled until
          icon: mdi:update
      title: Pi-hole
      show_header_toggle: false
  - type: conditional
    conditions:
      - condition: state
        entity: switch.pi_hole_group_single_macbook_air_bastien
        state: "off"
    card:
      type: entities
      entities:
        - entity: switch.pi_hole_group_single_macbook_air_bastien
        - type: attribute
          entity: switch.pi_hole_group_single_macbook_air_bastien
          attribute: remaining_seconds
          name: Remaining seconds
          icon: mdi:clock
        - type: attribute
          entity: switch.pi_hole_group_single_macbook_air_bastien
          attribute: until_date
          name: Disabled until
          icon: mdi:update
      title: "[single] Macbook Air Bastien"
      show_header_toggle: false
```
