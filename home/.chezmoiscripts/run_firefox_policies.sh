#!/bin/bash

sudo mkdir -p /etc/firefox
sudo tee /etc/firefox/policies/policies.json >/dev/null <<EOD
{
    "policies": {
        "PasswordManagerEnabled": false,
        "Preferences": {
            "browser.tabs.insertRelatedAfterCurrent": false,
            "browser.ml.chat.provider": "https://chat.badjware.dev/?temporary-chat=true&model=browser-assistant",
            "browser.ml.chat.prompts.3": "{\"label\":\"Validate code snippet\", \"value\":\"Please validate the selected code snippet. Assume any HTML entities are represented as their corresponding characters in the actual code. Assume that this snippet is part of a larger codebase. Identify and report any mistakes, syntax errors, and potential improvements. Do not report correct or reasonable code. Please ask if you require more context.\",\"targeting\":\"contentType != 'page'\"}",
            "browser.ml.linkPreview.enabled": false
        }
    }
}
EOD