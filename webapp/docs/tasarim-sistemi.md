# Tasarım sistemi — Vue 3 + Vite + Tailwind

Arayüz sıfırdan yazılıyor. Hedef: **oynanabilirlik**. Bu bir gösteri sayfası
değil, saatlerce bakılan bir oyun masası — okunabilirlik ve hızlı erişim her
şeyin önünde.

## 1. Yığın

- Vue 3 (`<script setup>`) + Vite
- Tailwind CSS v4 (CSS-first: `@import "tailwindcss"`, `@theme` ile token)
- Pinia (oyun durumu) + vue-router (`/` oyuncu, `/secrets` anlatıcı)
- Build çıktısı `../static/dist`, `base: '/static/dist/'` — Flask servis eder
- Dev: `npm run dev`, `/api` isteklerini `http://localhost:5050`'ye proxy'ler

## 2. Tipografi

**Inter** (variable woff2, yerel dosya — internet olmadan da çalışır).
Poppins yuvarlak ve geniş; yoğun oyun panellerinde satır sığmıyor. Inter dar
metrikleri ve rakam netliğiyle sayaç/envanter için daha iyi.

| Rol | Boyut / ağırlık |
|---|---|
| Sahne metni (ana okuma) | 16px / 1.7, 400 — ölçü 65-75 karakter |
| Panel başlığı | 12px, 600, `tracking-wide`, `uppercase` |
| Kart başlığı | 14px, 600 |
| Etiket / rozet | 11px, 500 |
| Sayaç rakamı | `tabular-nums` şart (zıplamasın) |

`font-feature-settings: "cv05","ss01"` — okunaklı `l`/`I` ayrımı.

## 3. Renk

Karanlık tema tek tema. Kıyamet paleti: soğuk kömür zemin, tek sıcak vurgu.

```css
@theme {
  --color-bg:        #0b0d0f;   /* sayfa */
  --color-surface:   #14181c;   /* panel */
  --color-surface-2: #1c2228;   /* kart, hover */
  --color-border:    #262e36;
  --color-text:      #e6e9ec;
  --color-muted:     #8b959f;
  --color-accent:    #d4703a;   /* tek sıcak vurgu — kızıl turuncu */
  --color-danger:    #d64545;
  --color-warn:      #d9a441;
  --color-ok:        #4f9d69;
  --color-gm:        #8b6bd4;   /* anlatıcı ekranına özel mor */
}
```

Kurallar: gerilim/severity renkleri **sadece** durum bildirir (düşük=ok,
orta=warn, yüksek/kritik=danger). Karakter renkleri sabit paletten türetilir
(mevcut `colorFor` mantığı korunur, isim → renk kararlı olsun).

## 4. Yerleşim — açılır/kapanır sidebar

```
┌──────────────────────────────────────────────────────────┐
│ ÜST BAR: ☰  Gün 98 · 21:40 gece · yağmurlu 7°C · konum   │
├────────────┬─────────────────────────────────────────────┤
│ SIDEBAR    │  BESTE ALANI                                │
│ (kapanır)  │  ┌─────────────────────────────────────┐    │
│            │  │ [Kimsin? ▾]  aksiyon yaz…    [Gönder]│   │
│ Kadro      │  └─────────────────────────────────────┘    │
│ Kaynaklar  │                                             │
│ Zorluklar  │  EN YENİ OLAY EN ÜSTTE ↓                    │
│ NPC'ler    │  ── tur 42 · Okan (zar 73) ────────────     │
│            │  ── tur 41 · anlatıcı ─────────────────     │
└────────────┴─────────────────────────────────────────────┘
```

- Sidebar `localStorage`'da hatırlanan açık/kapalı durum; kapalıyken sadece
  ikon şeridi (48px) kalır, tooltip ile isim. `Ctrl/Cmd + B` kısayolu.
- <1024px: sidebar üstten açılan çekmece (overlay), gövde kaymaz.
- **Oyun geçmişi en yeni en üstte.** Girdi alanı akışın ÜSTÜNDE sabit durur —
  yeni sahne yazının hemen altında belirir, kullanıcı aşağı kaymak zorunda
  kalmaz. Otomatik kaydırma yok; yeni içerik geldiğinde üstte "yeni sahne"
  rozeti yanıp söner.
- Anlatıcı ekranı (`/secrets`) aynı iskeleti kullanır; sidebar'da dünya zarı,
  plan, gizli notlar ve PIN kilidi bulunur. Vurgu rengi mor (`--color-gm`) ki
  yanlış ekranda oynanmasın.

## 5. İkonlar

**Material Symbols Rounded** (fonts.google.com/icons), variable woff2 yerel
dosya olarak `frontend/public/fonts/` altında. Tek `<Icon name="…" />`
bileşeni: `font-variation-settings` ile ağırlık/dolgu ayarlanır.

| Kullanım | İkon |
|---|---|
| menü / sidebar | `menu`, `left_panel_close`, `left_panel_open` |
| kadro | `groups`, `person` |
| envanter | `backpack` |
| kaynak | `inventory_2` |
| zorluk | `crisis_alert` |
| zar | `casino` |
| zaman | `schedule` |
| hava | `rainy`, `cloud`, `wb_sunny`, `ac_unit` |
| sağlık | `favorite`, `healing`, `bloodtype` |
| uyku/katılım | `bedtime`, `directions_walk`, `lock` |
| gönder | `send` |
| ayarlar / müzik | `settings`, `music_note` |
| anlatıcı | `visibility_off`, `bolt` |

Material Symbols'ta karşılığı olmayan bir şey çıkarsa **Lucide** (ISC
lisanslı, tree-shakeable) `lucide-vue-next` paketiyle eklenir; ikon adı yine
tek `Icon` bileşeninden geçer. Emoji ikon olarak kullanılmaz (mevcut arayüzde
emoji vardı — hepsi kalkıyor).

## 6. Bileşen envanteri

**Kabuk**: `AppShell`, `TopBar`, `SideBar`, `SidebarSection`, `Icon`, `Badge`,
`Panel`, `BaseButton`, `Modal`, `Tooltip`, `EmptyState`, `SkeletonLine`.

**Oyun**: `StoryFeed` (ters sıralı), `StoryEntry` (oyuncu/anlatıcı/sistem
varyantları), `ActionComposer` (karakter seçici + metin + gönder),
`CharacterCard` (durum, yaralar, vitals çubukları, envanter çipleri, katılım
rozeti), `CharacterModal`, `ResourcePanel`, `ChallengeList`, `NpcList`,
`DeathBanner`, `WorldClock`.

**Anlatıcı**: `PinGate`, `WorldDicePanel`, `GmNoteComposer` (üç mod),
`StatePatchEditor`, `PlotPanel` (senarist planı), `GmLog`.

## 7. Etkileşim kuralları

- Her istek durumunun üç hali görünür olacak: yükleniyor / hata / boş.
  Tur gönderildiğinde composer kilitlenir, ilerleme göstergesi çıkar
  (model yanıtı 30-60 sn sürebilir — kullanıcı ne olduğunu bilmeli).
- Yoklama (`/api/state?since=`) mevcut sürüm mantığıyla aynı kalır; Pinia
  store tek yerden yönetir.
- Klavye: `Enter` gönderir, `Shift+Enter` satır atlar, `Ctrl/Cmd+B` sidebar.
- Erişilebilirlik: her ikon düğmesinde `aria-label`, odak halkası görünür,
  kontrast en az AA.
- Hareket: sadece 120-180 ms geçişler; `prefers-reduced-motion` saygı görür.
