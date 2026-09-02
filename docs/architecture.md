# Architecture

```text
Next.js UI → FastAPI API → PostgreSQL
                       ├→ private object-storage adapter (documents)
                       ├→ Stripe Checkout + verified webhook
                       └→ transactional-email adapter
```

`QuoteRequest` is not an `Order`. An admin creates and sends a `Quote`; accepting it creates or reuses one customer `DRAFT` order and copies the price into `OrderItem` snapshot fields. New quote requests can remain associated with the continuing draft order, so multiple accepted quotes form one cart.

Allowed quote transitions are server enforced: `PENDING_REVIEW/PHARMACY_REVIEW → DRAFT → SENT → VIEWED/ACCEPTED/DECLINED/EXPIRED`. Orders proceed `DRAFT → PAYMENT_PENDING → CONFIRMED` in the currently implemented checkout path; operational fulfillment transitions should be exposed only to authorized internal roles.
