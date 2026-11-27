# Push notifications setup

GuardGo sends device notifications through the Expo Push API. Firebase and Apple credentials are uploaded to the Expo project using `eas credentials`; the backend does not hold those keys.

Set `EXPO_PUSH_ENABLED='true'` to enable push (the default), or `false` to disable delivery. Set `EXPO_ACCESS_TOKEN` to the Expo access token when enhanced push security is enabled; leave it empty otherwise. Keep access tokens out of committed files.

The backend needs outbound HTTPS access to `exp.host`, including from its Docker network. Run the cron process to check delivery receipts and clean up unregistered devices.
