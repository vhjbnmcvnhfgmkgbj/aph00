[app]
title = Jarvis
package.name = jarvis
package.domain = org.jarvisai
source.dir = .
source.include_exts = py,png,jpg,ttf,json
version = 2.0
requirements = python3,kivy==2.3.0,pyjnius,android,certifi,openssl,six,arabic-reshaper==3.0.0,python-bidi==0.4.2
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,QUERY_ALL_PACKAGES
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
