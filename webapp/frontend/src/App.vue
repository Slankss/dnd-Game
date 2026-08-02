<script setup>
/**
 * Kök bileşen — yalnızca rota görünümünü taşır. Ekranların kendi kabuğu
 * (AppShell) vardır; buraya iş mantığı girmez.
 */
</script>

<template>
  <RouterView v-slot="{ Component }">
    <component :is="Component" />
  </RouterView>
</template>
