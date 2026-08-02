<script setup>
/**
 * Senaryo ve oyun aktarma — dışa aktar (indir) / içe aktar (dosya seç).
 *
 * İçe aktarma ve varsayılana dönüş YIKICIDIR: sunucu dünya durumunu, oyun
 * günlüğünü ve anlatıcı defterini siler. Bu yüzden hepsi iki adımlıdır ve
 * onay penceresinde ne kaybedileceği açıkça yazar.
 */
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import Modal from '@/components/ui/Modal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import * as api from '@/api/client'

const emit = defineEmits(['degisti'])

/** Hangi iş uçuşta: '' | 'senaryo-disa' | 'oyun-disa' | 'onay' */
const mesgul = ref('')
const hata = ref('')
const bilgi = ref('')

const senaryoDosyasi = ref(null)
const oyunDosyasi = ref(null)

/** Onay penceresi durumu */
const onay = ref(null) // {baslik, aciklama, dugme, calistir}

function tarihEki() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`
}

function sifirla() {
  hata.value = ''
  bilgi.value = ''
}

/* ------------------------------------------------------------ dışa aktarma */

async function senaryoIndir() {
  sifirla()
  mesgul.value = 'senaryo-disa'
  try {
    const veri = await api.exportScenario()
    api.indirJson(veri, `senaryo-${tarihEki()}.json`)
    bilgi.value = 'Senaryo dosyası indirildi.'
  } catch (e) {
    hata.value = api.toApiError(e).message
  } finally {
    mesgul.value = ''
  }
}

async function oyunIndir() {
  sifirla()
  mesgul.value = 'oyun-disa'
  try {
    const veri = await api.exportGame()
    api.indirJson(veri, `oyun-kaydi-${tarihEki()}.json`)
    bilgi.value = 'Oyun kaydı indirildi.'
  } catch (e) {
    hata.value = api.toApiError(e).message
  } finally {
    mesgul.value = ''
  }
}

/* ------------------------------------------------------------ içe aktarma */

/** Seçilen dosyayı okuyup JSON'a çevirir; hata olursa Türkçe mesaj basar. */
async function dosyayiOku(olay) {
  const dosya = olay.target.files?.[0]
  olay.target.value = '' // aynı dosya tekrar seçilebilsin
  if (!dosya) return null
  try {
    return JSON.parse(await dosya.text())
  } catch {
    hata.value = `"${dosya.name}" geçerli bir JSON dosyası değil.`
    return null
  }
}

async function senaryoSecildi(olay) {
  sifirla()
  const veri = await dosyayiOku(olay)
  if (!veri) return
  if (typeof veri.scenario_text !== 'string' || !veri.scenario_text.trim()) {
    hata.value = 'Geçersiz senaryo dosyası: `scenario_text` eksik.'
    return
  }
  if (!veri.initial_world_state || typeof veri.initial_world_state !== 'object') {
    hata.value = 'Geçersiz senaryo dosyası: `initial_world_state` eksik.'
    return
  }
  onay.value = {
    baslik: 'Senaryoyu değiştir',
    aciklama:
      'Yeni senaryo yüklenince oyun BAŞTAN başlar: dünya durumu, oyun günlüğü ve ' +
      'anlatıcı defteri silinir. Devam etmeden önce mevcut oyunu dışa aktarmak isteyebilirsin.',
    dugme: 'Senaryoyu yükle',
    calistir: () => api.importScenario(veri),
    tamam: 'Yeni senaryo yüklendi, oyun sıfırlandı.',
  }
}

async function oyunSecildi(olay) {
  sifirla()
  const veri = await dosyayiOku(olay)
  if (!veri) return
  if (!veri.state || typeof veri.state !== 'object' || !veri.state.world_state) {
    hata.value = 'Geçersiz oyun dosyası: `state.world_state` eksik.'
    return
  }
  if (!Array.isArray(veri.log)) {
    hata.value = 'Geçersiz oyun dosyası: `log` bir liste olmalı.'
    return
  }
  onay.value = {
    baslik: 'Oyun kaydını yükle',
    aciklama:
      'Şu anki oyun tamamen değiştirilir: dünya durumu, günlük ve anlatıcı defteri ' +
      'dosyadakiyle yer değiştirir. Anlatıcı oturumu da sıfırlanır (hikaye geçmişi korunur).',
    dugme: 'Kaydı yükle',
    calistir: () => api.importGame(veri),
    tamam: 'Oyun kaydı yüklendi.',
  }
}

function varsayilanaDon() {
  sifirla()
  onay.value = {
    baslik: 'Varsayılan senaryoya dön',
    aciklama:
      'Özel senaryo dosyası silinir ve oyun varsayılan senaryoyla BAŞTAN başlar. ' +
      'Mevcut dünya durumu, günlük ve anlatıcı defteri kaybolur.',
    dugme: 'Varsayılana dön',
    calistir: () => api.resetScenarioDefault(),
    tamam: 'Varsayılan senaryoya dönüldü.',
  }
}

async function onayla() {
  if (!onay.value) return
  mesgul.value = 'onay'
  try {
    await onay.value.calistir()
    bilgi.value = onay.value.tamam
    onay.value = null
    emit('degisti')
  } catch (e) {
    hata.value = api.toApiError(e).message
    onay.value = null
  } finally {
    mesgul.value = ''
  }
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- Oyun kaydı -->
    <section class="flex flex-col gap-1.5">
      <h3 class="text-panel uppercase tracking-[0.06em] text-muted">Oyun kaydı</h3>
      <p class="text-label text-faint">
        Dünya durumu + oyun günlüğü + anlatıcı defteri. Riskli bir müdahaleden önce indir.
      </p>
      <div class="flex flex-wrap gap-2">
        <BaseButton
          icon="download"
          :loading="mesgul === 'oyun-disa'"
          loading-text="Hazırlanıyor…"
          @click="oyunIndir"
        >
          Oyunu dışa aktar
        </BaseButton>
        <BaseButton icon="upload_file" variant="subtle" @click="oyunDosyasi?.click()">
          Oyunu içe aktar
        </BaseButton>
        <input
          ref="oyunDosyasi"
          type="file"
          accept="application/json,.json"
          class="hidden"
          aria-label="Oyun kaydı dosyası seç"
          @change="oyunSecildi"
        />
      </div>
    </section>

    <!-- Senaryo -->
    <section class="flex flex-col gap-1.5 border-t border-border pt-3">
      <h3 class="text-panel uppercase tracking-[0.06em] text-muted">Senaryo</h3>
      <p class="text-label text-faint">
        Anlatıcının kurallar metni ve başlangıç dünyası. Değiştirmek oyunu sıfırlar.
      </p>
      <div class="flex flex-wrap gap-2">
        <BaseButton
          icon="download"
          :loading="mesgul === 'senaryo-disa'"
          loading-text="Hazırlanıyor…"
          @click="senaryoIndir"
        >
          Senaryoyu dışa aktar
        </BaseButton>
        <BaseButton icon="upload_file" variant="subtle" @click="senaryoDosyasi?.click()">
          Senaryoyu içe aktar
        </BaseButton>
        <BaseButton icon="restart_alt" variant="danger" @click="varsayilanaDon">
          Varsayılana dön
        </BaseButton>
        <input
          ref="senaryoDosyasi"
          type="file"
          accept="application/json,.json"
          class="hidden"
          aria-label="Senaryo dosyası seç"
          @change="senaryoSecildi"
        />
      </div>
    </section>

    <p v-if="hata" class="flex items-start gap-1.5 text-meta text-danger" role="alert">
      <Icon name="error" :size="16" class="mt-0.5 shrink-0" />
      <span>{{ hata }}</span>
    </p>
    <p v-else-if="bilgi" class="flex items-center gap-1.5 text-meta text-ok" role="status">
      <Icon name="check_circle" :size="16" />
      {{ bilgi }}
    </p>

    <!-- Yıkıcı işlem onayı -->
    <Modal
      :model-value="!!onay"
      tone="gm"
      icon="warning"
      :title="onay?.baslik || ''"
      size="md"
      @update:model-value="onay = null"
    >
      <p class="text-meta text-text">{{ onay?.aciklama }}</p>
      <p class="mt-2 flex items-start gap-1.5 text-label text-warn">
        <Icon name="warning" :size="14" class="mt-0.5 shrink-0" />
        <span>Bu işlem geri alınamaz.</span>
      </p>
      <template #footer>
        <BaseButton variant="subtle" icon="close" @click="onay = null">Vazgeç</BaseButton>
        <BaseButton
          variant="danger"
          icon="check_circle"
          :loading="mesgul === 'onay'"
          loading-text="Uygulanıyor…"
          @click="onayla"
        >
          {{ onay?.dugme }}
        </BaseButton>
      </template>
    </Modal>
  </div>
</template>
