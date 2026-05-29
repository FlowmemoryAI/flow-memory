# Flow Memory Capacity Market

Flow Memory Capacity Market models standardized compute units, capacity windows, dry-run holds, non-binding reservations, utilization, and order-book views.

```mermaid
flowchart TD
    Provider[Capacity provider] --> Window[Capacity window]
    Window --> Inventory[Capacity inventory]
    Buyer[Agent or workspace] --> Quote[Capacity quote]
    Inventory --> Quote
    Quote --> Hold[Dry-run hold]
    Hold --> Reservation[Non-binding reservation]
    Reservation --> Utilization[Utilization record]
    Reservation --> Release[Release or expire]
```

## CLI

```bash
flow-memory capacity inventory --json
flow-memory capacity quote --gpu-class H100 --region us-east --hours 100 --json
flow-memory capacity reserve --gpu-class H100 --region us-east --hours 10 --json
flow-memory capacity index --gpu-class H100 --region us-east --json
flow-memory capacity forward-curve --gpu-class H100 --region us-east --json
flow-memory capacity forward quote --gpu-class H100 --hours 100 --json
```

## API

- `GET /capacity/inventory`
- `POST /capacity/quote`
- `POST /capacity/hold`
- `POST /capacity/reserve`
- `POST /capacity/release`
- `GET /capacity/reservations`
- `GET /capacity/utilization`
- `GET /capacity/order-book`

All reservations are dry-run and non-binding: `funds_moved=false`, `legally_binding=false`.

## Reservation accounting

Capacity windows are treated as a dry-run inventory book. Creating a hold decrements the selected window's `available_units`; releasing the reservation restores those units exactly once. Repeating the same hold or release is idempotent, so a retry cannot double-consume or double-restore simulated capacity.

```mermaid
sequenceDiagram
    participant Buyer as Agent or workspace
    participant Market as Capacity Market
    participant Window as Capacity Window
    participant Store as Compute Store
    Buyer->>Market: POST /capacity/reserve
    Market->>Window: Check available units
    Window-->>Market: Capacity available
    Market->>Window: Decrement available units
    Market->>Store: Persist hold and reservation
    Buyer->>Market: POST /capacity/release
    Market->>Window: Restore reserved units once
    Market->>Store: Persist released reservation
```
