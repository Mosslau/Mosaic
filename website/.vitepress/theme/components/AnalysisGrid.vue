<script setup>
import curriculum from '../../data/curriculum.json'

defineProps({
  heading: { type: Boolean, default: true },
})

const pad = (n) => String(n).padStart(2, '0')
const analysis = curriculum.analysis
</script>

<template>
  <section class="section">
    <h2 v-if="heading" class="section__head">
      语言设计分析
      <span class="section__note">每篇笔记配一个可运行 demo，末尾标注「对 Tenet 的启示」</span>
    </h2>

    <ul class="lattice lattice--analysis">
      <li
        v-for="item in analysis"
        :key="item.id"
        class="an"
        :style="{ '--accent': `var(--t-${item.token})` }"
      >
        <a class="an__head" :href="item.link">
          <span class="an__name">{{ item.name }}</span>
          <span class="an__thesis">{{ item.thesis }}</span>
        </a>
        <ol class="an__notes">
          <li v-for="note in item.notes" :key="note.n">
            <a class="an__note" :href="note.link">
              <span class="an__n">{{ pad(note.n) }}</span>
              <span class="an__t">{{ note.title }}</span>
            </a>
          </li>
        </ol>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.an {
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: background var(--t-dur) var(--t-ease);
}

.an:hover {
  background: color-mix(in srgb, var(--accent) 6%, var(--t-surface));
}

.an__head {
  display: grid;
  gap: 9px;
  padding: 24px 24px 18px;
  text-decoration: none;
}

.an__name {
  font-family: var(--vp-font-family-mono);
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.012em;
  color: var(--accent);
}

.an__thesis {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--t-ink-2);
}

.an__notes {
  margin: auto 0 0;
  padding: 0 12px 12px;
  list-style: none;
}

.an__note {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 7px 12px;
  border-radius: var(--t-radius);
  font-size: 13.5px;
  color: var(--t-ink-2);
  text-decoration: none;
  transition: background var(--t-dur) var(--t-ease), color var(--t-dur) var(--t-ease);
}

.an__note:hover,
.an__note:focus-visible {
  background: var(--t-surface-sunken);
  color: var(--t-ink);
}

.an__n {
  font-family: var(--vp-font-family-mono);
  font-size: 12px;
  color: var(--t-ink-3);
  font-variant-numeric: tabular-nums;
}

.lattice--analysis > li {
  min-height: 100%;
}
</style>
