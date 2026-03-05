#!/bin/bash

sudo mkdir -p /etc/firefox
sudo tee /etc/firefox/policies/policies.json >/dev/null <<EOD
{
    "policies": {
        "GenerativeAI": {
            "LinkPreviews": false
        },
        "PasswordManagerEnabled": false
        "Preferences": {
            "browser.ml.chat.provider": "https://chat.badjware.dev/?temporary-chat=true&model=Qwen3.5-35B-A3B"
        }
    }
}
EOD