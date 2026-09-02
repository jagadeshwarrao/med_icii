# Microsoft Graph email setup

Medicii supports Microsoft Graph application delivery for quote-reviewed and verified-order notifications.

## Configure the Entra application

1. In **App registrations** open **Medicii Email Service**.
2. Under **API permissions**, add Microsoft Graph **Application** permission `Mail.Send` and have a tenant administrator grant consent.
3. Under **Certificates & secrets**, create a short-lived client secret for local development. Store its **Value** only in the local `.env`; it is not retrievable after leaving Entra.
4. Ensure `noreply@medicii.net` is an active Exchange Online mailbox. Restrict the application's mailbox access to this mailbox using an Exchange application access policy before production.

## Local configuration

Add these values to `.env` (do not commit the file):

```env
GRAPH_TENANT_ID=f5632797-4369-47fb-b1e9-86820a3ce06e
GRAPH_CLIENT_ID=6ae0edb0-8249-49ee-b6e3-7fea8e25fd8f
GRAPH_CLIENT_SECRET=private-client-secret-value
GRAPH_SENDER=noreply@medicii.net
```

Then rebuild with `docker compose up --build -d`.

For production, use a certificate or workload identity kept in Azure Key Vault rather than a client secret. The app uses the OAuth client-credentials flow and Microsoft Graph `POST /users/{sender}/sendMail`; a successful request returns no message body.
