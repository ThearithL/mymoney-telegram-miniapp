# Render + Neon — Admin approval setup

## ១. Upload project

ជំនួស code ក្នុង GitHub ជាមួយ version នេះ។ កុំ upload `.env` ឬលុប Neon Database ចាស់។ បើ repository មាន folder `mymoney-miniapp` ដាក់ Render Root Directory ជា folder នោះ។

## ២. Render Environment

| Key | តម្លៃ |
|---|---|
| BOT_TOKEN | Token ពេញរបស់ @MoneyNoteKHBot ពី BotFather |
| APP_URL | https://mymoney-telegram-miniapp.onrender.com |
| WEBHOOK_SECRET | secret ថ្មីដែលអ្នករក្សាទុកជាសម្ងាត់ |
| DATABASE_URL | Neon PostgreSQL connection URL ពេញ ជាមួយ SSL parameters |
| ADMIN_USER_ID | ដំបូងទុកទទេ បើមិនទាន់ស្គាល់ ID របស់ខ្លួន |
| ADMIN_PASSWORD_HASH | Hash ពាក្យសម្ងាត់ Admin (កុំដាក់ពាក្យសម្ងាត់ធម្មតា) |
| FLASK_SECRET_KEY | Generate secret ក្នុង Render; រក្សាវាឱ្យនៅដដែល |
| ALLOWED_USER_IDS | ទុកទទេ ឬ ID ពិតរបស់អ្នកដែលអនុញ្ញាតជាមុន |
| PYTHON_VERSION | 3.12.14 |

APP_URL ត្រូវដូច URL ពិតរបស់ Render service របស់អ្នក។ កុំដាក់ Bot ID ក្នុង ADMIN_USER_ID។ កុំបញ្ចូល secret ក្នុង GitHub ឬ chat។

## ៣. Commands

Build Command:

```bash
pip install -r requirements.txt
```

Start Command (copy ទាំងបន្ទាត់):

```bash
python setup_bot.py && gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60
```

វានឹងភ្ជាប់ webhook, callbacks និងប៊ូតុង MyMoney នៅពេល service ចាប់ផ្ដើម។ មិនចាំបាច់ run PowerShell setup ទៀតទេ។ ប្រើ Bot Token នេះសម្រាប់ service នេះតែមួយ។

Deploy → រង់ចាំ Live។ ពិនិត្យ Logs ថាមាន `setWebhook: OK`, `setChatMenuButton: OK`, `setMyCommands: OK`។ បើ setup បរាជ័យ server មិនចាប់ផ្ដើមទេ; កែ Token/URL/Secret តាម log រួច deploy ម្ដងទៀត។

## ៤. កំណត់ខ្លួនឯងជា Admin

1. ផ្ញើ `/id` ទៅ @MoneyNoteKHBot។ វាអាចឆ្លើយបាន ទោះមិនទាន់មានសិទ្ធិ Mini App ក៏ដោយ។
2. Copy លេខ ID ផ្ទាល់ខ្លួនដែល Bot ឆ្លើយ។
3. ដាក់លេខនោះក្នុង Render `ADMIN_USER_ID` ហើយ Save and deploy។
4. ផ្ញើ `/start` ទៅ Bot ពីគណនី Admin នោះ ដើម្បីទទួល notification។

បង្កើត password hash ក្នុង PowerShell ក្រោយ install requirements:

```powershell
.venv\Scripts\python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('New Admin password: ')))"
```

Copy hash ទៅ Render `ADMIN_PASSWORD_HASH` ហើយកំណត់ `FLASK_SECRET_KEY` ជា secret ថ្មី។ Deploy រួច បើក Settings → Admin Console ហើយបញ្ចូល password។ ផ្ទាំងចាក់សោវិញស្វ័យប្រវត្តិក្រោយ ១៥ នាទី ឬចុច **Lock Admin**។ បញ្ចូលខុស ៥ ដង នឹងរង់ចាំ ១៥ នាទី។

## ៥. អនុញ្ញាតអ្នកប្រើថ្មី

អ្នកប្រើ → `/start` → ចុច `Request access`។
Admin → ទទួលឈ្មោះ និង ID → ចុច `Approve` ឬ `Reject`។
អ្នកប្រើដែលបានអនុញ្ញាត → បិទ Mini App និងបើកម្ដងទៀត។ មិនចាំបាច់ redeploy ទេ។

ដើម្បីបន្ថែមពី Admin Console តាម ID ឬ `@username` សូមឱ្យគណនីនោះផ្ញើ `/start` ឬ `/request` ទៅ Bot មុន។ Telegram មិនអនុញ្ញាតឱ្យ Bot ស្វែងរក username ដែលមិនធ្លាប់ឃើញទេ។ អ្នកអាចសាកល្បងដោយប្រើគណនី Telegram ទីពីររបស់អ្នក។

បើមិនទទួល notification ផ្ញើ `/requests` ពី Admin ដើម្បីមើលសំណើ pending ៥ ក្នុងមួយលើក។ គ្មានអ្នកប្រើផ្សេងអាចចុចអនុញ្ញាតជំនួស Admin បានទេ។

អ្នកប្រើម្នាក់ៗមានទិន្នន័យផ្ទាល់ខ្លួន។ Admin អាចមើលកំណត់ត្រារបស់អ្នកប្រើតាម /admin ក្នុង Telegram។ Mini App API បង្ហាញតែទិន្នន័យរបស់អ្នកប្រើដែលបានចូល។

Neon រក្សាទុកសិទ្ធិ និងទិន្នន័យក្រៅ Render។ Render Free នៅតែអាច sleep ហើយ Bot អាចឆ្លើយយឺតពេលភ្ញាក់ឡើងវិញ។

## ជួយកុំឱ្យ Render Free sleep

Project មាន health URL រួចហើយ៖ `https://mymoney-telegram-miniapp.onrender.com/health`។ វាត្រឡប់ HTTP 200 និង `{"ok": true}`។ Render health check មិនអាចទប់ការគេងរបស់ Free service បានទេ។

ដើម្បីសាកល្បង keep-alive ដោយមិនចាំបាច់បង់ប្រាក់៖

1. បង្កើត monitor ប្រភេទ **HTTP(s)** នៅសេវា uptime monitor ខាងក្រៅ ដូចជា UptimeRobot Free។
2. ដាក់ URL `https://mymoney-telegram-miniapp.onrender.com/health` និង interval **5 minutes**។
3. រក្សាទុក monitor ហើយពិនិត្យថាស្ថានភាពបង្ហាញ **Up**។

Request ខាងក្រៅរៀងរាល់ 5 នាទីអាចជួយកុំឱ្យ Render មើលឃើញថា service គ្មាន traffic 15 នាទី។ វាជា workaround ប៉ុណ្ណោះ៖ Render អាច restart Free service បានគ្រប់ពេល ហើយមិនមានការធានា uptime 24/24 ទេ។

## Update ថ្មី

Upload ឯកសារទាំងអស់ក្នុង ZIP ជំនួសកូដចាស់ រួមទាំង admin_panel.py និង static ទាំងមូល។ រក្សា DATABASE_URL របស់ Neon ដដែល។ Deploy រួចផ្ញើ /start ហើយ /admin ពីគណនីម្ចាស់។

សារព្រមានថវិកា 80% និង 100% ផ្ញើពេលរក្សាទុកចំណាយ ឬថវិកាសម្រាប់ខែបច្ចុប្បន្ន។ មិនមែនជាសារផ្ញើតាមម៉ោងដោយស្វ័យប្រវត្តិទេ។

## កំណែ UI / ក្រាហ្វរង្វង់ / លុបច្រើន

Upload ឯកសារទាំងអស់ រួមទាំង static/design.js, design.css និង history.js។ ម៉ាស៊ីនគិតលេខត្រូវបានដកចេញ។

History → ជ្រើសរើស → ជ្រើសកំណត់ត្រា → លុបដែលបានជ្រើស។ «លុបកំណត់ត្រារបស់ខ្ញុំទាំងអស់» លុបចំណូលនិងចំណាយគ្រប់ខែ គ្រប់រូបិយប័ណ្ណរបស់អ្នក។ ត្រូវវាយ DELETE មុនបញ្ជាក់។ ថវិកានិងគោលដៅសន្សំនៅដដែល។ ការលុបផ្លាស់ទៅធុងសំរាម ហើយអាចស្ដារវិញបានតាម Settings → ធុងសំរាម។

ក្រាហ្វរង្វង់ និងក្រាហ្វប្រចាំថ្ងៃនៅ Menu របាយការណ៍។ កំណត់ថវិកាតាមប៊ូតុង «កំណត់» នៅកាតថវិកាទំព័រដើម។

## Profile / ស្ដារ / រូបបង្កាន់ដៃ

Upload កូដទាំងអស់ រួមទាំង personal_features.py និង static/features.js។ Build Command នៅតែ pip install -r requirements.txt (មាន Pillow ថ្មី)។

Settings → Profile៖ កែឈ្មោះ និងព័ត៌មានខ្លី។ Settings → ធុងសំរាម៖ ស្ដារ ឬលុបជាអចិន្ត្រៃយ៍។ ចុចកំណត់ត្រាចំណាយ → ជ្រើសរូប → រក្សាទុករូប (JPEG/PNG/WebP ≤ 2 MB)។ រូបនៅក្នុង Neon។

Home → ថវិកា → កំណត់៖ បន្ថែមថវិកាតាមប្រភេទ។ របាយការណ៍ → ប្រៀបធៀបខែ៖ ខែនេះមិនទាន់ចប់ នឹងមានសម្គាល់ច្បាស់។

Header រូបភ្នែក៖ បិទបាំងចំនួនប្រាក់ក្នុង Browser នេះ។ ចំណូលចិត្ត៖ កត់ចំណាយញឹកញាប់បានរហ័ស រហូតដល់ 12 គំរូ។ គំរូបំពេញ Draft មុន—អ្នកអាចពិនិត្យ ឬកែចំនួន មុនចុចរក្សាទុក។
