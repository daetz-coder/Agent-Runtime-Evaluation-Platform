import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard.vue'),
          meta: { title: '仪表板', icon: 'DataBoard' },
        },
        {
          path: 'tasks',
          name: 'Tasks',
          component: () => import('@/views/Tasks.vue'),
          meta: { title: '任务管理', icon: 'List' },
        },
        {
          path: 'tasks/:id',
          name: 'TaskDetail',
          component: () => import('@/views/TaskDetail.vue'),
          meta: { title: '任务详情', hidden: true },
        },
        {
          path: 'evaluations',
          name: 'Evaluations',
          component: () => import('@/views/Evaluations.vue'),
          meta: { title: '评估记录', icon: 'Document' },
        },
        {
          path: 'evaluations/:id',
          name: 'EvaluationDetail',
          component: () => import('@/views/EvaluationDetail.vue'),
          meta: { title: '评估详情', hidden: true },
        },
        {
          path: 'analytics',
          name: 'Analytics',
          component: () => import('@/views/Analytics.vue'),
          meta: { title: '数据分析', icon: 'TrendCharts' },
        },
        {
          path: 'benchmark',
          name: 'Benchmark',
          component: () => import('@/views/Benchmark.vue'),
          meta: { title: '单调性基准', icon: 'Histogram' },
        },
        {
          path: 'wiki-agent',
          name: 'WikiAgent',
          component: () => import('@/views/WikiAgent.vue'),
          meta: { title: 'Wiki Agent', icon: 'Reading', fullBleed: true },
        },
        {
          path: 'settings',
          name: 'Settings',
          component: () => import('@/views/Settings.vue'),
          meta: { title: '系统设置', icon: 'Setting' },
        },
      ],
    },
  ],
})

// Navigation guard
router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'Agent Evaluation'} - Agent Evaluation Platform`
  next()
})

export default router
