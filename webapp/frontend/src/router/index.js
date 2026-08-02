import { createRouter, createWebHistory } from 'vue-router'
import PlayerView from '@/views/PlayerView.vue'

/**
 * Rotalar — Flask her iki yolu da aynı SPA ile karşılar (docs/mimari.md §4).
 *
 * DİKKAT: rota tabanı `/`'dir, `import.meta.env.BASE_URL` DEĞİL. Varlıklar
 * `/static/dist/` altından servis edilir ama sayfa adresleri `/` ve `/secrets`
 * olarak kalır.
 */
const routes = [
  {
    path: '/',
    name: 'player',
    component: PlayerView,
    meta: { title: 'Kızıl Çöküş' },
  },
  {
    path: '/secrets',
    name: 'gm',
    // Anlatıcı ekranı ayrı parça: oyuncular bu kodu hiç indirmesin.
    component: () => import('@/views/GmView.vue'),
    meta: { title: 'Anlatıcı Ekranı — Kızıl Çöküş' },
  },
  // Bilinmeyen yol → oyuncu ekranı
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory('/'),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  if (to.meta?.title) document.title = to.meta.title
})

export default router
