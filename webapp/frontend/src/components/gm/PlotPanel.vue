<script setup>
/**
 * Plan paneli (senarist katmanı) — HENÜZ VERİ YOK.
 *
 * `data/plot.json` sunucuda duruyor ama hiçbir uç nokta onu yayınlamıyor:
 * `/api/gm/state` yalnızca `world_state`, `gm_log` ve `log` döndürüyor. Plan
 * arayüzü senarist-yetenegi.md Faz 3'te (`GET/POST /api/gm/plot`) açılacak.
 *
 * Burada UYDURMA veri göstermiyoruz — anlatıcı olmayan bir plana güvenip
 * sahne kurarsa oyun bozulur.
 */
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'

defineProps({
  /** Yan panel varyantı */
  compact: { type: Boolean, default: false },
})

/** Faz 2/3 geldiğinde bu panelde görünecek bölümler. */
const BEKLENEN = [
  { ikon: 'account_tree', ad: 'İplikler', tanim: 'sürmekte olan olay örgüleri (`threads`)' },
  { ikon: 'bolt', ad: 'Beat\'ler', tanim: 'koşullu randevular: bekleyen / ateşlenmiş / vadesi dolmuş' },
  { ikon: 'lightbulb', ad: 'Tohumlar', tanim: 'henüz hasat edilmemiş ipuçları (`seeds`)' },
]
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex flex-wrap items-center gap-2">
      <Badge tone="muted" icon="pending">Faz 2'de bağlanacak</Badge>
    </div>

    <p class="text-meta text-muted">
      Senarist planı (<code class="font-mono text-label">data/plot.json</code>) henüz API'den
      gelmiyor. Sunucu bu ekrana yalnızca dünya durumunu, oyun günlüğünü ve anlatıcı
      notlarını yolluyor.
    </p>

    <ul v-if="!compact" class="flex flex-col gap-1">
      <li
        v-for="b in BEKLENEN"
        :key="b.ad"
        class="flex items-start gap-2 rounded-card border border-border bg-surface-2 px-2.5 py-1.5"
      >
        <Icon :name="b.ikon" :size="15" class="mt-0.5 shrink-0 text-faint" />
        <span class="text-label text-muted"><b class="text-text">{{ b.ad }}</b> — {{ b.tanim }}</span>
      </li>
    </ul>

    <p class="text-label text-faint">
      O zamana kadar plan yerine <b>gizli yönlendirme</b> modunu kullan: yazdığın not
      anlatıcının hafızasına girer ve sonraki turlarda hayata geçer.
    </p>
  </div>
</template>
