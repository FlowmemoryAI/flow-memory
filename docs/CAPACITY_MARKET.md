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
