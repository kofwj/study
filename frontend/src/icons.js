// 共享图标映射：科目图标 + 等级图标（把后端存的 emoji 映射成 Lucide 组件）
import {
    BookOpen, Calculator, Globe, FlaskConical, Heart, Dumbbell, Palette, Sparkles,
    Sprout, Leaf, Flower, Star, Flame, Trophy, Medal, Gem, Rocket, Crown,
} from 'lucide-vue-next'

export const SUBJECT_ICONS = {
    语文: BookOpen,
    数学: Calculator,
    英语: Globe,
    科学: FlaskConical,
    道法: Heart,
    体育: Dumbbell,
    音美: Palette,
    综合: Sparkles,
}

const RANK_ICONS = {
    sprout: Sprout, leaf: Leaf, flower: Flower, star: Star, flame: Flame,
    trophy: Trophy, medal: Medal, gem: Gem, rocket: Rocket, crown: Crown,
    '🌱': Sprout, '🌿': Leaf, '🌼': Flower, '⭐': Star, '🔥': Flame,
    '🏆': Trophy, '🥇': Medal, '💎': Gem, '🚀': Rocket, '👑': Crown,
}

export function rankIcon(glyph) {
    return RANK_ICONS[glyph] || Star
}