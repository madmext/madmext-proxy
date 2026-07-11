# OneSignal Bildirim Merkezi Kurulumu

## Railway ortam değişkenleri

Aşağıdaki değişkenleri Madmext Ads Railway servisinde tanımlayın:

```text
ONESIGNAL_APP_ID=<OneSignal App ID>
ONESIGNAL_REST_API_KEY=<OneSignal App REST API Key>
```

Opsiyonel:

```text
ONESIGNAL_API_BASE=https://api.onesignal.com
```

API anahtarı frontend'e gönderilmez. Tüm OneSignal çağrıları Flask backend üzerinden yapılır.

## İlk kullanım

1. Railway deploy tamamlandıktan sonra Madmext Ads'e admin hesabıyla giriş yapın.
2. Sol menüden **Bildirim Merkezi** sayfasını açın.
3. **OneSignal'dan Senkronize Et** düğmesine basın.
4. İlk senkronizasyonda PostgreSQL tabloları otomatik oluşturulur.

## Oluşturulan tablolar

- `onesignal_messages`
- `onesignal_sync_runs`

## Endpoint'ler

- `GET /onesignal/status`
- `POST /onesignal/sync` — yalnızca admin
- `GET /onesignal/dashboard?days=30`
- `GET /onesignal/messages?days=30&limit=500&q=`
- `GET /onesignal/export.csv`

## Güvenlik

- REST API anahtarı yalnızca Railway ortam değişkeninde saklanır.
- Senkronizasyon işlemi admin rolü gerektirir.
- Panel hiçbir endpoint'ten API anahtarı değerini alamaz.
- Ham OneSignal yanıtları hata ayıklama ve yeniden işleme için PostgreSQL JSONB alanında saklanır.

## Bu sürümün kapsamı

İlk sürüm mesaj geçmişini, gönderim/teslim/tıklama/hata metriklerini, dönem filtrelerini, aramayı ve CSV dışa aktarımı sağlar. Kullanıcı/abonelik CSV aktarımı, Event Streams webhook'ları, segmentler ve Ticimax sipariş-ciro eşleştirmesi sonraki fazlarda eklenmelidir.
