#!/bin/bash
systemctl --user daemon-reload
systemctl --user enable --now swayidle.service
systemctl --user enable --now wob.service
systemctl --user enable --now mako.service