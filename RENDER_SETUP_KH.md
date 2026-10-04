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

## ៥. អនុញ្ញាតអ្នកប្រើថ្មី

អ្នកប្រើ → `/start` → ចុច `Request access`។
Admin → ទទួលឈ្មោះ និង ID → ចុច `Approve` ឬ `Reject`។
អ្នកប្រើដែលបានអនុញ្ញាត → បិទ Mini App និងបើកម្ដងទៀត។ មិនចាំបាច់ redeploy ទេ។

បើមិនទទួល notification ផ្ញើ `/requests` ពី Admin ដើម្បីមើលសំណើ pending ៥ ក្នុងមួយលើក។ គ្មានអ្នកប្រើផ្សេងអាចចុចអនុញ្ញាតជំនួស Admin បានទេ។

អ្នកប្រើម្នាក់ៗមានទិន្នន័យផ្ទាល់ខ្លួន។ Admin អាចមើលកំណត់ត្រារបស់អ្នកប្រើតាម /admin ក្នុង Telegram។ Mini App API បង្ហាញតែទិន្នន័យរបស់អ្នកប្រើដែលបានចូល។

Neon រក្សាទុកសិទ្ធិ និងទិន្នន័យក្រៅ Render។ Render Free នៅតែអាច sleep ហើយ Bot អាចឆ្លើយយឺតពេលភ្ញាក់ឡើងវិញ។

## Update ថ្មី

Upload ឯកសារទាំងអស់ក្នុង ZIP ជំនួសកូដចាស់ រួមទាំង admin_panel.py និង static ទាំងមូល។ រក្សា DATABASE_URL របស់ Neon ដដែល។ Deploy រួចផ្ញើ /start ហើយ /admin ពីគណនីម្ចាស់។

សារព្រមានថវិកា 80% និង 100% ផ្ញើពេលរក្សាទុកចំណាយ ឬថវិកាសម្រាប់ខែបច្ចុប្បន្ន។ មិនមែនជាសារផ្ញើតាមម៉ោងដោយស្វ័យប្រវត្តិទេ។

## កំណែ UI / ក្រាហ្វរង្វង់ / លុបច្រើន

Upload ឯកសារទាំងអស់ រួមទាំង static/design.js, design.css និង history.js។ ម៉ាស៊ីនគិតលេខត្រូវបានដកចេញ។

History → ជ្រើសរើស → ជ្រើសកំណត់ត្រា → លុបដែលបានជ្រើស។ «លុបកំណត់ត្រារបស់ខ្ញុំទាំងអស់» លុបចំណូលនិងចំណាយគ្រប់ខែ គ្រប់រូបិយប័ណ្ណរបស់អ្នក។ ត្រូវវាយ DELETE មុនបញ្ជាក់។ ថវិកានិងគោលដៅសន្សំនៅដដែល។ ការលុបមិនអាច Undo បានទេ។

ក្រាហ្វរង្វង់ និងក្រាហ្វប្រចាំថ្ងៃនៅ Menu របាយការណ៍។ កំណត់ថវិកាតាមប៊ូតុង «កំណត់» នៅកាតថវិកាទំព័រដើម។
