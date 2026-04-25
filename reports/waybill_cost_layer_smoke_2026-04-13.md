# Waybill Cost Layer

- source file: `/home/user/mm-market-tools/data/local/waybill_synthetic_sample.json`
- sheet: `Товары на отправку`
- raw rows: `3`
- normalized rows: `3`
- unmatched rows: `0`
- rows with barcode: `3`
- rows with cogs: `3`
- total quantity supplied: `27`
- total batch cogs: `3260.0 ₽`

## Column mapping

- `barcode` -> `Штрихкод`
- `cogs` -> `Себестоимость`
- `quantity` -> `Количество`
- `title` -> `Наименование`
- `sku` -> `Артикул`
- `product_id` -> `н/д`
- `upd_id` -> `УПД`
- `planned_supply_at` -> `Дата поставки`
- `waybill_id` -> `Номер накладной`

## Historical COGS snapshot

- `4601234567890` | latest cogs `130.0` ₽ | batches `2` | title `Игрушка А`
- `4601234567891` | latest cogs `89.0` ₽ | batches `1` | title `Игрушка Б`