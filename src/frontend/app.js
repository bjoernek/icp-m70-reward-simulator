// Voting Rewards Scenario Explorer
// Ported from voting_rewards_app_v2.py

const SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60;
const TS = 550776194;  // total supply (ICP)
const R = 0.0575;      // reward rate (5.75%)
const SCALE = 1e8;

let neuronGroups = [];

// --- Core functions (ported from Python) ---

function mapDissolveDelays(ddYears, newMaxDelayYears) {
  return Math.min(ddYears, newMaxDelayYears);
}

function dissolveDelayBonusConvex(xYears, maxDelayYears, maxBonus, minBonus, n) {
  var xCapped = Math.min(xYears, maxDelayYears);
  var a = (maxBonus - minBonus) / Math.pow(maxDelayYears, n);
  return a * Math.pow(xCapped, n) + minBonus;
}

function computeMetrics(params) {
  var newVpSum = 0;
  var currentVpSum = 0;
  var eightYearSeconds = 8.0 * SECONDS_PER_YEAR;

  for (var i = 0; i < neuronGroups.length; i++) {
    var g = neuronGroups[i];
    var ddSeconds = g[0];
    var weightedStake = g[1];
    var groupCurrentVp = g[2];
    var is8y = g[3];

    currentVpSum += groupCurrentVp;

    var ddYears = ddSeconds / SECONDS_PER_YEAR;
    var mappedDd = mapDissolveDelays(ddYears, params.maxDelayYears);

    if (mappedDd >= params.minDelayYears) {
      var bonus = dissolveDelayBonusConvex(mappedDd, params.maxDelayYears, params.maxBonus, 1.0, params.n);
      var groupNewVp = weightedStake * bonus;
      if (is8y) groupNewVp *= params.eightYearBonus;
      newVpSum += groupNewVp;
    }
  }

  currentVpSum /= SCALE;
  newVpSum /= SCALE;

  var ddBonusOld = 1 + params.maxDelayYears / 8.0;
  var ddBonusNew = params.maxBonus;
  var alpha = ddBonusOld / ddBonusNew * (newVpSum / currentVpSum) / params.eightYearBonus;
  var inflationReduction = Math.round((1 - alpha) * 10000) / 100;

  return {
    inflationReduction: inflationReduction,
    newVpSum: newVpSum,
    currentVpSum: currentVpSum,
    alpha: alpha
  };
}

// --- Chart setup ---

var pieChart, bonusChart, apyChart;

function createCharts() {
  pieChart = new Chart(document.getElementById("pieChart"), {
    type: "doughnut",
    data: {
      labels: ["Reduced", "Remaining"],
      datasets: [{
        data: [0, 100],
        backgroundColor: ["#4caf50", "#e0e0e0"],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      plugins: {
        title: { display: true, text: "Inflation Breakdown" },
        legend: { position: "bottom" }
      },
      animation: { duration: 150 }
    }
  });

  bonusChart = new Chart(document.getElementById("bonusChart"), {
    type: "line",
    data: { labels: [], datasets: [{ data: [], borderColor: "#4a6fa5", borderWidth: 2, pointRadius: 0, fill: false }] },
    options: {
      responsive: true,
      plugins: {
        title: { display: true, text: "Dissolve Delay Bonus" },
        legend: { display: false }
      },
      scales: {
        x: { title: { display: true, text: "Dissolve delay (years)" }, type: "linear" },
        y: { title: { display: true, text: "Bonus" } }
      },
      animation: { duration: 150 }
    }
  });

  apyChart = new Chart(document.getElementById("apyChart"), {
    type: "line",
    data: { labels: [], datasets: [{ data: [], borderColor: "#e67e22", borderWidth: 2, pointRadius: 0, fill: false }] },
    options: {
      responsive: true,
      plugins: {
        title: { display: true, text: "Neuron APY (%)" },
        legend: { display: false }
      },
      scales: {
        x: { title: { display: true, text: "Dissolve delay (years)" }, type: "linear" },
        y: { title: { display: true, text: "Neuron APY (%)" } }
      },
      animation: { duration: 150 }
    }
  });

}

// --- Read parameters from DOM ---

function getParams() {
  var maxDelay = parseFloat(document.getElementById("maxDelay").value);
  var minDelayMonths = parseFloat(document.getElementById("minDelay").value);
  return {
    maxDelayYears: maxDelay,
    minDelayYears: minDelayMonths / 12.0,
    maxBonus: parseFloat(document.getElementById("maxBonus").value),
    n: parseFloat(document.getElementById("convexityN").value),
    eightYearBonus: parseFloat(document.getElementById("eightYearBonus").value)
  };
}

// --- Generate curve data ---

function linspace(start, end, n) {
  var arr = new Array(n);
  var step = (end - start) / (n - 1);
  for (var i = 0; i < n; i++) arr[i] = start + i * step;
  return arr;
}

// --- Update everything ---

function updateAll() {
  var params = getParams();

  // Update slider displays
  document.getElementById("maxDelayValue").textContent = params.maxDelayYears;
  document.getElementById("minDelayValue").textContent = (params.minDelayYears * 12).toFixed(1);

  // Compute metrics
  var metrics = computeMetrics(params);

  var rawInfl = metrics.inflationReduction;
  var displayInfl = Math.abs(rawInfl) < 0.01 ? 0.0 : rawInfl;
  document.getElementById("inflationMetric").textContent = displayInfl.toFixed(2);

  var alpha = 1 - rawInfl / 100;

  // Pie chart
  var reduced = Math.max(0, Math.min(100, rawInfl));
  var remaining = Math.max(0, 100 - reduced);
  pieChart.data.datasets[0].data = [reduced, remaining];
  pieChart.update();

  // Bonus curve (200 points, 0 to maxDelayYears)
  var NUM_POINTS = 200;
  var xBonus = linspace(0, params.maxDelayYears, NUM_POINTS);
  var yBonus = xBonus.map(function(x) {
    return dissolveDelayBonusConvex(x, params.maxDelayYears, params.maxBonus, 1.0, params.n);
  });

  bonusChart.data.datasets[0].data = xBonus.map(function(x, i) { return { x: x, y: yBonus[i] }; });
  bonusChart.update();

  // APY curve
  var vpConvex = metrics.newVpSum;
  var yApy;
  if (vpConvex > 0) {
    yApy = xBonus.map(function(x, i) {
      if (x < params.minDelayYears) return 0;
      return yBonus[i] * TS / vpConvex * R * 100 * alpha;
    });
  } else {
    yApy = xBonus.map(function() { return 0; });
  }

  apyChart.data.datasets[0].data = xBonus.map(function(x, i) { return { x: x, y: yApy[i] }; });
  apyChart.update();

  // Max APY metrics (no age bonus means age_bonus=1, so APY = bonus * TS / vp * R * alpha * 100)
  if (vpConvex > 0) {
    var maxApyNoAge = params.maxBonus * TS / vpConvex * R * 100 * alpha;
    var maxApyNoAge8y = maxApyNoAge * params.eightYearBonus;
    document.getElementById("maxApyMetric").textContent = maxApyNoAge.toFixed(2) + "%";
    document.getElementById("maxApy8yMetric").textContent = maxApyNoAge8y.toFixed(2) + "%";
  } else {
    document.getElementById("maxApyMetric").textContent = "--";
    document.getElementById("maxApy8yMetric").textContent = "--";
  }
}

// --- Initialization ---

async function init() {
  var response = await fetch("data/neuron_groups.json");
  var data = await response.json();
  neuronGroups = data.groups;

  createCharts();

  // Wire up event listeners
  var controls = ["maxDelay", "minDelay", "maxBonus", "convexityN", "eightYearBonus"];
  controls.forEach(function(id) {
    var el = document.getElementById(id);
    el.addEventListener("input", updateAll);
    el.addEventListener("change", updateAll);
  });

  updateAll();
}

init();
