# Deployment Guide

## GitHub Setup
1. Create a private GitHub repository.
2. Push this project to the repository.
3. Add these GitHub Actions secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `REDIS_URL`

## Schedule
The workflow runs every 4 days using `.github/workflows/daily_check.yml`.

## Manual Trigger
Open the repository `Actions` tab and run the workflow manually whenever you want to test it.

## Notes
- The app now scrapes only `AcademicTransfer` and `EURAXESS`.
- The tracker stores sent IDs in Redis using a hashed key per job ID.
- Repeated vacancies are skipped automatically on later runs.
