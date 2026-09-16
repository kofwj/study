<script setup>
// 秘密基地 tab 页 + 阳光图鉴弹窗 + 玩具店 + 值班/改名详情 + 晨报。
// 共享状态（sprites/scene/图鉴开合/晨报）在 store；信封点击 emit('open-capsule') 交父级开胶囊弹窗。
import { ref, reactive } from 'vue'
import { House } from '@lucide/vue'
import { api } from '../api.js'
import {
  sprites, capsule, spriteScene, spritesOpen, morningShow, toyFlip,
  spImg, toyImg, baseImg, displayName, sceneToys, sceneBuddies,
  loadSprites, maybeShowMorning, showToast,
} from '../store.js'

const emit = defineEmits(['open-capsule'])

const spriteDetail = ref(null)
const spriteNick = ref('')
const spriteFlavor = ref('')
const spriteBusy = ref(false)
const toyShopOpen = ref(false)

function openSprites() {
  loadSprites()
  if (!sprites.value.enabled && !sprites.value.base_enabled) return
  spritesOpen.value = true
  maybeShowMorning()
}
defineExpose({ openSprites })
function openSpriteCell(it) {
  if (!it.owned) { showToast('连续打卡开宝箱才会遇到它'); return }
  spriteDetail.value = it
  spriteNick.value = it.nickname || ''
  spriteFlavor.value = it.flavor || ''
}
async function saveSpriteProfile() {
  const it = spriteDetail.value
  if (!it) return
  try {
    const out = await api.spriteProfile(it.id, { nickname: spriteNick.value, flavor: spriteFlavor.value })
    Object.assign(it, out)
    showToast('已记住')
    await loadSprites()
  } catch (e) { showToast(e.message) }
}
async function starSprite() {
  const it = spriteDetail.value
  if (!it) return
  try {
    const out = await api.spriteStar(it.id)
    it.stars = out.stars
    sprites.value.dust = out.dust
    showToast('亮了一颗星')
  } catch (e) { showToast(e.message) }
}
async function buyToy(id) {
  if (spriteBusy.value) return
  spriteBusy.value = true
  try {
    const out = await api.baseBuy(id)
    sprites.value.dust = out.dust
    sprites.value.base_items = out.base_items
    showToast('放到秘密基地啦')
  } catch (e) { showToast(e.message) }
  finally { spriteBusy.value = false }
}
async function toggleDuty(id) {
  try {
    const on = sprites.value.on_duty === id
    const out = on ? await api.spriteDutyClear() : await api.spriteDuty(id)
    sprites.value.on_duty = out.on_duty
  } catch (e) { showToast(e.message) }
}
async function ackMorning() {
  morningShow.value = false
  try { await api.morningAck() } catch {}
  if (sprites.value.morning) sprites.value.morning.new = false
}
</script>

<template>
  <!-- 秘密基地 tab 页 -->
  <template v-if="sprites.base_enabled">
    <h1 class="base-head">
      <span><House class="ico" :size="20" /> 秘密基地</span>
      <span v-if="sprites.enabled" class="dust-chip">星尘 {{ sprites.dust }}</span>
      <button v-if="sprites.enabled" type="button" class="do" @click="toyShopOpen = true">玩具店</button>
    </h1>
    <div v-if="morningShow && sprites.morning?.text" class="morning-note" @click="ackMorning">
      <img v-if="sprites.morning.who" class="duty-face" :src="spImg(sprites.morning.who)" alt="" />
      <div>
        <strong>昨晚报</strong>
        <p>{{ sprites.morning.text }}</p>
        <small>点一下收好</small>
      </div>
    </div>
    <div class="atlas-scene-tabs">
      <button type="button" class="tab" :class="{ on: spriteScene === 'sun' }" @click="spriteScene = 'sun'">天台</button>
      <button type="button" class="tab" :class="{ on: spriteScene === 'leaf' }" @click="spriteScene = 'leaf'">树屋</button>
      <button type="button" class="tab" :class="{ on: spriteScene === 'sky' }" @click="spriteScene = 'sky'">云上</button>
    </div>
    <div class="atlas-stage atlas-stage-page" :class="{ 'moon-full': sprites.enabled && spriteScene === 'sky' && sprites.today?.review_clear }">
      <img class="atlas-bg" :src="baseImg(spriteScene)" alt="" />
      <div v-if="!sprites.enabled" class="atlas-building"><b>建设中</b><span>图鉴打开以后，朋友才搬进来</span></div>
      <template v-if="sprites.enabled" v-for="t in sceneToys(spriteScene)" :key="'p'+t.id">
        <div class="atlas-toy" :class="[t.anim, { flip: toyFlip[t.id], ready: t.id === 'memo-capsule' && capsule.state === 'ready', sealed: t.id === 'memo-capsule' && capsule.state === 'sealed' }]"
          :style="{ left: t.x + '%', top: t.y + '%', width: t.w + '%' }"
          @click="t.id === 'memo-capsule' ? emit('open-capsule') : (t.flip && (toyFlip[t.id] = !toyFlip[t.id]))">
          <template v-if="t.id === 'trace-pinwheel'">
            <img class="stick" :src="toyImg('trace-pinwheel-stick')" alt="" />
            <img class="blades" :src="toyImg('trace-pinwheel-blades')" alt="" />
          </template>
          <template v-else-if="t.id === 'memo-flag'">
            <img class="pole" :src="toyImg('memo-flag-pole')" alt="" />
            <img class="fabric" :src="toyImg('memo-flag-fabric')" alt="" />
          </template>
          <div v-else-if="t.id === 'memo-capsule'" class="capsule-letter"><span class="flap"></span><span class="sheet"></span></div>
          <img v-else class="toy" :src="toyImg(t.id)" :alt="t.name" />
        </div>
      </template>
      <template v-if="sprites.enabled">
        <img v-for="b in sceneBuddies(spriteScene)" :key="'pb'+b.id" class="atlas-buddy"
          :src="spImg(b.id)" :alt="displayName(b)"
          :style="{ left: b.x + '%', top: b.y + '%', width: b.w + '%' }" />
      </template>
      <img v-if="sprites.enabled && spriteScene === 'sun' && sprites.today?.unit_done" class="atlas-plane" :src="toyImg('trace-plane')" alt="" />
      <span v-if="sprites.enabled && spriteScene === 'sky' && sprites.today?.word_done" class="atlas-star">✦</span>
    </div>
  </template>
  <div v-else class="coming-page">
    <div class="coming">
      <House class="ico" :size="36" />
      <strong>秘密基地</strong>
      <em>建设中</em>
      <p>小房子还在搭，以后可以藏贴纸、日记和悄悄话。</p>
    </div>
  </div>

  <!-- 阳光图鉴弹窗 -->
  <div v-if="spritesOpen" class="mask" @click.self="spritesOpen = false">
    <div class="shop-modal ach-modal atlas-modal">
      <h3 class="base-head">{{ sprites.enabled ? ('阳光图鉴 ' + sprites.owned + '/12') : '秘密基地' }} <span v-if="sprites.enabled" class="dust-chip">星尘 {{ sprites.dust }}</span></h3>
      <div class="ach-body">
        <div v-if="morningShow && sprites.morning?.text" class="morning-note" @click="ackMorning">
          <img v-if="sprites.morning.who" class="duty-face" :src="spImg(sprites.morning.who)" alt="" />
          <div>
            <strong>昨晚报</strong>
            <p>{{ sprites.morning.text }}</p>
            <small>点一下收好</small>
          </div>
        </div>
        <div v-if="sprites.base_enabled" class="atlas-scene-tabs">
          <button type="button" class="tab" :class="{ on: spriteScene === 'sun' }" @click="spriteScene = 'sun'">天台</button>
          <button type="button" class="tab" :class="{ on: spriteScene === 'leaf' }" @click="spriteScene = 'leaf'">树屋</button>
          <button type="button" class="tab" :class="{ on: spriteScene === 'sky' }" @click="spriteScene = 'sky'">云上</button>
        </div>
        <div v-if="sprites.base_enabled" class="atlas-stage" :class="{ 'moon-full': sprites.enabled && spriteScene === 'sky' && sprites.today?.review_clear }">
          <img class="atlas-bg" :src="baseImg(spriteScene)" alt="" />
          <div v-if="!sprites.enabled" class="atlas-building"><b>建设中</b><span>图鉴打开以后，朋友才搬进来</span></div>
          <template v-if="sprites.enabled" v-for="t in sceneToys(spriteScene)" :key="t.id">
            <div class="atlas-toy" :class="[t.anim, { flip: toyFlip[t.id], ready: t.id === 'memo-capsule' && capsule.state === 'ready', sealed: t.id === 'memo-capsule' && capsule.state === 'sealed' }]"
              :style="{ left: t.x + '%', top: t.y + '%', width: t.w + '%' }"
              @click="t.id === 'memo-capsule' ? emit('open-capsule') : (t.flip && (toyFlip[t.id] = !toyFlip[t.id]))">
              <template v-if="t.id === 'trace-pinwheel'">
                <img class="stick" :src="toyImg('trace-pinwheel-stick')" alt="" />
                <img class="blades" :src="toyImg('trace-pinwheel-blades')" alt="" />
              </template>
              <template v-else-if="t.id === 'memo-flag'">
                <img class="pole" :src="toyImg('memo-flag-pole')" alt="" />
                <img class="fabric" :src="toyImg('memo-flag-fabric')" alt="" />
              </template>
              <div v-else-if="t.id === 'memo-capsule'" class="capsule-letter"><span class="flap"></span><span class="sheet"></span></div>
              <img v-else class="toy" :src="toyImg(t.id)" :alt="t.name" />
            </div>
          </template>
          <template v-if="sprites.enabled">
            <img v-for="b in sceneBuddies(spriteScene)" :key="'b'+b.id" class="atlas-buddy"
              :src="spImg(b.id)" :alt="displayName(b)"
              :style="{ left: b.x + '%', top: b.y + '%', width: b.w + '%' }" />
          </template>
          <img v-if="sprites.enabled && spriteScene === 'sun' && sprites.today?.unit_done" class="atlas-plane" :src="toyImg('trace-plane')" alt="" />
          <span v-if="sprites.enabled && spriteScene === 'sky' && sprites.today?.word_done" class="atlas-star">✦</span>
        </div>
        <details v-if="sprites.enabled" v-for="g in sprites.series" :key="g.id" class="ach-series" open>
          <summary>{{ g.name }} {{ g.owned }}/{{ g.total }}</summary>
          <div class="ach-grid">
            <div v-for="it in g.items" :key="it.id" class="ach-cell" :class="{ on: it.owned }" @click="openSpriteCell(it)">
              <img v-if="it.owned" class="atlas-cell-face" :src="spImg(it.id)" :alt="displayName(it)" />
              <div v-else class="atlas-sil"></div>
              <div class="ach-name">{{ it.owned ? displayName(it) : '？？' }}</div>
              <div v-if="it.owned" class="ach-prog">{{ '★'.repeat(it.stars) }}{{ '☆'.repeat(3 - it.stars) }}</div>
            </div>
          </div>
        </details>
        <p v-if="sprites.enabled && sprites.base_enabled" class="dim atlas-shop-hint">玩具在秘密基地的玩具店里买。</p>
      </div>
      <button class="ghost" @click="spritesOpen = false">关闭</button>
    </div>
    <div v-if="spriteDetail" class="ach-pop" @click.self="spriteDetail = null">
      <div class="ach-detail">
        <img class="box-face" :src="spImg(spriteDetail.id)" :alt="displayName(spriteDetail)" />
        <h3>{{ spriteDetail.name }}</h3>
        <p class="dim">{{ spriteDetail.flavor }}</p>
        <p>{{ '★'.repeat(spriteDetail.stars) }}{{ '☆'.repeat(3 - spriteDetail.stars) }}</p>
        <label class="fld companion-name"><span>昵称</span>
          <input v-model="spriteNick" maxlength="8" placeholder="1 到 8 个字" />
        </label>
        <label class="fld companion-name"><span>一句介绍</span>
          <input v-model="spriteFlavor" maxlength="16" placeholder="最多 16 个字" />
        </label>
        <button type="button" class="do" @click="saveSpriteProfile">保存</button>
        <button type="button" class="ghost" :disabled="spriteDetail.stars >= 3 || sprites.dust < sprites.star_cost" @click="starSprite">
          {{ spriteDetail.stars >= 3 ? '已经三颗星了' : (sprites.star_cost + ' 星尘升一星') }}
        </button>
        <button v-if="sprites.base_enabled" type="button" class="ghost" @click="toggleDuty(spriteDetail.id)">
          {{ sprites.on_duty === spriteDetail.id ? '取消值班' : '设为值班' }}
        </button>
        <button type="button" class="ghost" @click="spriteDetail = null">关闭</button>
      </div>
    </div>
  </div>

  <!-- 玩具店 -->
  <div v-if="toyShopOpen" class="mask" @click.self="toyShopOpen = false">
    <div class="shop-modal enter toy-shop-modal">
      <h3>玩具店</h3>
      <p class="dust-chip toy-shop-dust">你有星尘 {{ sprites.dust }}</p>
      <div class="toy-shop-grid">
        <div v-for="it in sprites.shop" :key="it.id" class="toy-shop-card" :class="{ have: it.owned }">
          <img :src="toyImg(it.id)" :alt="it.name" />
          <b>{{ it.name }}</b>
          <span>{{ it.price }} 星尘</span>
          <button v-if="it.owned" type="button" class="ghost" disabled>已有</button>
          <button v-else type="button" class="do" :disabled="spriteBusy || sprites.dust < it.price" @click="buyToy(it.id)">换</button>
        </div>
      </div>
      <button class="ghost" @click="toyShopOpen = false">关闭</button>
    </div>
  </div>
</template>

<style scoped>
/* —— 从 App.vue 搬来（页专属样式）—— */
@media (max-width: 1100px) {
    .atlas-stage-page { max-width: none; }
}
@media (max-width: 700px) {
    .atlas-stage { margin-left: -4px; margin-right: -4px; width: calc(100% + 8px); border-radius: 10px; }
}
  .atlas-stage { position: relative; width: 100%; aspect-ratio: 1448 / 543; border-radius: 12px; overflow: hidden; background: #1a1410; margin-bottom: 12px; }
  .atlas-stage-page { max-width: 920px; overflow: visible; }
  .atlas-building {
  position: absolute; inset: 0; z-index: 8;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  background: rgba(26,20,16,.42); color: #fffdf8; text-align: center; pointer-events: none;
}
  .atlas-building b { font-size: 22px; letter-spacing: .12em; }
  .atlas-building span { font-size: 13px; opacity: .9; }
  .atlas-bg { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; pointer-events: none; }
  .atlas-buddy { position: absolute; transform: translate(-50%, -100%); z-index: 5; filter: drop-shadow(0 2px 3px rgba(0,0,0,.3)); pointer-events: none; }
  .atlas-plane { position: absolute; width: 10%; top: 28%; left: -12%; animation: plane-fly 4.5s linear infinite; z-index: 6; }
  .atlas-star { position: absolute; left: 18%; top: 14%; color: #ffe9a8; font-size: 18px; filter: drop-shadow(0 0 6px #ffe9a8); }
  .atlas-stage.moon-full::after {
  content: "";
  position: absolute;
  left: 86.5%;
  top: 12.6%;
  width: 7.2%;
  aspect-ratio: 1;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  box-shadow: 0 0 22px 10px rgba(255, 244, 210, .45);
  animation: moon-glow 2.4s ease-in-out infinite;
}
  .atlas-cell-face { width: 48px; height: 48px; object-fit: contain; }
  .atlas-sil { width: 48px; height: 48px; margin: 0 auto; border-radius: 50%; background: var(--ink); opacity: .18; }
  .dust-chip {
  display: inline-flex; align-items: center; font-size: 14px; font-weight: 700;
  background: var(--warm-2); color: var(--accent-ink); padding: 4px 12px; border-radius: 999px;
}
  .toy-shop-dust { margin: 0 0 12px; }
  .toy-shop-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; margin: 8px 0 14px; }
  .toy-shop-card {
  display: flex; flex-direction: column; align-items: center; gap: 4px; text-align: center;
  background: var(--surface-2); border-radius: var(--radius-lg); padding: 12px 8px;
}
  .toy-shop-card img { width: 72px; height: 72px; object-fit: contain; }
  .toy-shop-card.have { opacity: .55; }
  .toy-shop-card b { font-size: 14px; }
  .toy-shop-card span { font-size: 12px; color: var(--ink-2); }
  .atlas-shop-hint { margin: 8px 0 0; font-size: 13px; }
</style>
