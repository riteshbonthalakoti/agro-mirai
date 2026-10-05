# Real SMS OTP (Module 56)

Farmer login is name + phone + a 6-digit OTP (`agro_mirai.auth.otp`).
How that code reaches the farmer is a swappable provider
(`agro_mirai.auth.otp_providers`), picked by `OTP_PROVIDER`:

| `OTP_PROVIDER` | What happens | Allowed in production? |
|---|---|---|
| `log` (default) | Code is written to the server log only. | No — app refuses to start. |
| `test` | Numbers in `OTP_TEST_NUMBERS` get a fixed code; no SMS sent. | Only with `ALLOW_TEST_OTP=1`. |
| `sms_gateway` | Real SMS via a spare Android phone. | Yes. |

## Setting up the spare Android phone (sms_gateway)

Free option, reaches any Indian number without a DLT registration: an
Android phone with an Indian SIM running the open-source
[SMS Gateway for Android](https://github.com/capcom6/android-sms-gateway)
(capcom6, Apache-2.0) in **cloud mode** — it relays ordinary texts
through the phone's own SIM.

1. Install the app from the Play Store or the project's GitHub releases page.
2. Open it, grant SMS permission when prompted.
3. Settings → Battery → disable battery optimisation for the app (it
   must keep running in the background).
4. If the phone is a recent Android version and the app was
   side-loaded (not from the Play Store), Android may hide it behind
   "Restricted settings" — Settings → Apps → SMS Gateway → the
   three-dot menu → **Allow restricted settings**, before the
   permission prompts above will work.
5. Switch the app to **cloud mode** and sign in / register — this
   gives you the username and password for `SMS_GATEWAY_USER` /
   `SMS_GATEWAY_PASS` below.
6. Keep the phone charged and connected to the internet (Wi-Fi or
   mobile data) at all times — it is the only thing standing in for
   an SMS provider, so if it goes offline, OTPs stop reaching anyone.

It's a demo tool, not a provider: carriers may throttle or flag heavy
traffic from a single consumer SIM. Fine for a handful of real
logins; move to a paid provider before any real traffic volume (see
below).

## Setting the env vars on Render

```bash
render env set OTP_PROVIDER=sms_gateway --service <your-service-id>
render env set SMS_GATEWAY_USER=<gateway-username> --service <your-service-id>
render env set SMS_GATEWAY_PASS=<gateway-password> --service <your-service-id>
```

(Or set them in the Render dashboard under the service's Environment
tab, then trigger a redeploy — either way, the app re-reads them at
startup and refuses to start if `OTP_PROVIDER=log` was left set.)

## Testing without burning a real SMS

Set `OTP_PROVIDER=test` and `OTP_TEST_NUMBERS=+91xxxxxxxxxx:123456` for
local dev or a reviewer who needs a login without wiring up the phone.
This is explicitly refused in production unless `ALLOW_TEST_OTP=1` is
also set — a demo override, not a default.

## Production upgrade path

The spare-phone setup is a demo stand-in. For real production volume,
swap `sms_gateway` for a paid provider — add one more `OtpSender`
subclass in `agro_mirai/auth/otp_providers.py` and one more branch in
`build_otp_sender`, no change needed in `api/routes/auth_v2.py`:

- **2Factor** (~₹0.18/OTP) — has an India-specific OTP API, no DLT
  template registration needed for transactional OTP traffic.
- **MSG91** — similar pricing/positioning, also India-focused.

Twilio's free trial only sends to pre-verified numbers (up to 3), so
it doesn't work for farmer-facing OTP even as a stopgap.
