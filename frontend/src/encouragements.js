// 鼓励文案库
export const encouragements = {
  // 任务完成
  taskComplete: [
    '太棒了',
    '真厉害',
    '你最棒',
    '做得好',
    '又进步了',
    '继续保持',
    '很不错',
    '加油',
    '真努力',
    '好样的',
  ],
  
  // 连续打卡
  streak: {
    3: ['连续3天，有毅力', '坚持3天了，真棒', '3天连击，继续'],
    7: ['一周都没断，厉害', '7天连击，你是打卡机器', '坚持一周了，佩服'],
    14: ['两周不间断，太强了', '14天连击，无人能敌', '半个月都在坚持，了不起'],
    30: ['一个月都在坚持，你简直是传奇', '30天连击，你已经无敌了', '坚持整整一个月，你是榜样'],
  },
  
  // 根据时段
  morning: ['早起的鸟儿有阳光', '早上就这么努力，赞', '美好的一天从打卡开始'],
  afternoon: ['下午也在努力，给你点赞', '午后学习，效率高', '坚持学习，真棒'],
  evening: ['傍晚还在坚持，厉害', '晚上也不松懈，佩服', '今天又是充实的一天'],
  night: ['这么晚还在努力，记得早点休息哦', '夜深了，注意休息', '学习要劳逸结合，别太累'],
  
  // 根据阳光数量
  bigReward: ['哇，好多阳光', '一次得这么多，太赚了', '阳光大丰收'],
  
  // 破纪录
  newRecord: ['破纪录了', '创造新纪录', '又超越了自己'],
  
  // 签到
  checkin: ['签到成功', '今天来啦', '又见面了'],
  
  // 取消
  cancel: ['没关系，下次继续', '调整一下再来', '别灰心'],
}

// 获取随机鼓励文案
export function getEncouragement(context = {}) {
  const { type = 'taskComplete', streak, timeOfDay, reward, isRecord } = context
  
  // 连续打卡特殊文案
  if (streak >= 3) {
    const thresholds = [30, 14, 7, 3]
    for (const t of thresholds) {
      if (streak >= t && encouragements.streak[t]) {
        return random(encouragements.streak[t])
      }
    }
  }
  
  // 破纪录
  if (isRecord) {
    return random(encouragements.newRecord)
  }
  
  // 大奖励
  if (reward >= 20) {
    return random(encouragements.bigReward)
  }
  
  // 根据时段
  if (timeOfDay) {
    const hour = new Date().getHours()
    if (hour < 8 && encouragements.morning) return random(encouragements.morning)
    if (hour >= 8 && hour < 12 && encouragements.afternoon) return random(encouragements.afternoon)
    if (hour >= 12 && hour < 18 && encouragements.afternoon) return random(encouragements.afternoon)
    if (hour >= 18 && hour < 22 && encouragements.evening) return random(encouragements.evening)
    if (hour >= 22 && encouragements.night) return random(encouragements.night)
  }
  
  // 默认鼓励
  return random(encouragements[type] || encouragements.taskComplete)
}

function random(arr) {
  return arr[Math.floor(Math.random() * arr.length)]
}

// 伙伴互动文案（根据伙伴状态）
export function getCompanionMessage(companionStage, action = 'complete') {
  const messages = {
    egg: {
      complete: ['蛋壳里传来了欢呼', '小家伙很开心', '蛋在摇晃，好像很激动'],
    },
    sprout: {
      complete: ['小芽在为你加油', '嫩芽说：真棒', '小芽长高了一点点'],
    },
    leaf: {
      complete: ['叶子在风中摇曳，好像在鼓掌', '树叶说：你最棒', '叶子闪闪发光'],
    },
    bloom: {
      complete: ['花儿都为你骄傲', '花瓣在跳舞', '花香更浓了'],
    },
  }
  
  const stageMessages = messages[companionStage]?.[action]
  return stageMessages ? random(stageMessages) : null
}
