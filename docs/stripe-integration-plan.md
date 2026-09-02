# Stripe integration plan for Medicii.net

## 1. Payments: start here

Use Stripe-hosted Checkout for each confirmed quote cart. The API creates the Checkout Session only after recalculating prices from immutable order-item snapshots; the browser only receives the returned Checkout URL. Enable the `checkout.session.completed` and asynchronous payment events in Stripe, and treat the signature-verified webhook—not the customer return URL—as the payment source of truth.

Configure `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and `APP_URL` as deployment secrets. Never commit them. Rotate any secret key shared in chat. The publishable key is optional for hosted Checkout, and is the only key that may be placed in `NEXT_PUBLIC_*` configuration.

## 2. Tax: enable only after tax review

Set `STRIPE_TAX_ENABLED=true` only after registering tax obligations and configuring registrations in Stripe Tax. The integration then supplies `automatic_tax` to Checkout. Checkout uses collected shipping/billing location to calculate tax. Ensure product tax codes and shipping treatment are reviewed by tax counsel before production.

## 3. Invoicing

The Checkout integration can use `invoice_creation` to generate a Stripe invoice/receipt for a completed one-time payment. If Medicii needs payment-before-fulfillment invoices, add a separate admin-only invoice workflow and use Stripe webhooks to reconcile its status to the order; do not mark the order paid from a browser action.

## 4. Connect: phase after pharmacy verification

Do not onboard pharmacies or transfer funds until business, licensing, geography, refunds, dispute ownership, and compliance requirements are approved. For a single pharmacy per order, destination charges can route funds to that connected pharmacy and retain Medicii's platform fee. For one order involving several pharmacies, use separate charges and transfers after fulfillment policy approval. Store only each pharmacy's Stripe connected-account ID; use Stripe-hosted/embedded onboarding rather than collecting bank identity data yourself.

## 5. Test checklist

1. Create a new **restricted test-mode** secret key and add it locally to `.env`.
2. Set a Stripe CLI or Dashboard webhook endpoint to `/api/v1/stripe/webhook` and add its signing secret.
3. Submit a test order, pay with a Stripe test card, and verify one payment, one audit event, and a confirmed order.
4. Replay the same webhook event and verify it creates no duplicate payment.
5. Test a failed/async payment, cancellation, refund, and authorized access to order information.

Stripe products do not by themselves establish healthcare, pharmacy, privacy, tax, or regulatory compliance.
