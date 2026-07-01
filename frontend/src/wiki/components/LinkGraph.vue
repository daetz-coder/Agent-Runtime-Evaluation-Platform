<template>
  <div class="link-graph">
    <div class="graph-header">
      <h2>知识图谱</h2>
      <span class="graph-desc">页面之间的链接关系（共 {{ graphData.nodes.length }} 个节点，{{ graphData.links.length }} 条链接）</span>
    </div>

    <div v-if="loading" class="graph-loading">加载中...</div>
    <div v-else-if="graphData.nodes.length === 0" class="graph-empty">暂无数据</div>
    <v-chart v-else class="graph-chart" :option="chartOption" autoresize @click="handleClick" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { GraphChart } from "echarts/charts";
import { TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

use([GraphChart, TooltipComponent, LegendComponent, CanvasRenderer]);

const emit = defineEmits(["navigate"]);

const loading = ref(true);
const graphData = ref({ nodes: [], links: [] });

// 分类颜色映射
const CATEGORY_COLORS = {
  platform: "#5470c6",
  programming: "#91cc75",
  projects: "#fac858",
  notes: "#ee6666",
  architecture: "#73c0de",
  database: "#3ba272",
  protocol: "#fc8452",
  security: "#9a60b4",
  "getting-started": "#ea7ccc",
  docs: "#48b8d0",
};

const DEFAULT_COLOR = "#999";

async function loadGraph() {
  loading.value = true;
  try {
    const res = await fetch("/api/wiki/graph");
    const data = await res.json();
    graphData.value = data;
  } catch (e) {
    console.error("加载图谱失败:", e);
  } finally {
    loading.value = false;
  }
}

const chartOption = computed(() => {
  const { nodes, links } = graphData.value;

  // 收集所有 category
  const categories = [...new Set(nodes.map((n) => n.category).filter(Boolean))];

  // 计算每个节点的链接数（用于大小加权）
  const linkCount = {};
  for (const l of links) {
    linkCount[l.source] = (linkCount[l.source] || 0) + 1;
    linkCount[l.target] = (linkCount[l.target] || 0) + 1;
  }

  return {
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        if (params.dataType === "node") {
          const d = params.data;
          return `<b>${d.name}</b><br/>路径: ${d.path}<br/>分类: ${d.category || "无"}<br/>链接数: ${linkCount[d.id] || 0}`;
        }
        return `${params.data.source} → ${params.data.target}`;
      },
    },
    legend: {
      data: categories,
      orient: "vertical",
      right: 10,
      top: 40,
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        label: {
          show: true,
          position: "right",
          fontSize: 11,
          color: "#333",
        },
        categories: categories.map((c) => ({ name: c })),
        data: nodes.map((n) => ({
          id: n.id,
          name: n.title,
          path: n.path,
          category: n.category,
          symbolSize: Math.max(15, Math.min(50, 10 + (linkCount[n.id] || 0) * 8)),
          itemStyle: {
            color: CATEGORY_COLORS[n.category] || DEFAULT_COLOR,
          },
        })),
        links: links.map((l) => ({
          source: l.source,
          target: l.target,
        })),
        force: {
          repulsion: 200,
          gravity: 0.1,
          edgeLength: [80, 200],
          layoutAnimation: true,
        },
        lineStyle: {
          color: "#ccc",
          curveness: 0.1,
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 3 },
        },
      },
    ],
  };
});

function handleClick(params) {
  if (params.dataType === "node" && params.data.path) {
    emit("navigate", params.data.path);
  }
}

onMounted(loadGraph);
</script>

<style scoped>
.link-graph {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 24px 32px;
}

.graph-header {
  margin-bottom: 16px;
}

.graph-header h2 {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.graph-desc {
  font-size: 13px;
  color: #888;
}

.graph-loading,
.graph-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 14px;
}

.graph-chart {
  flex: 1;
  min-height: 400px;
}
</style>
