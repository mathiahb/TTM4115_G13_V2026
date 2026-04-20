const map = L.map("map").setView([63.4305, 10.3951], 13);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
}).addTo(map);

let shops = [];
let selectedShop = null;
let currentOrder = null;
let activeRoute = null;
let pollTimer = null;
let previousView = null;

function saveView() {
    previousView = { center: map.getCenter(), zoom: map.getZoom() };
}

function restoreView() {
    if (previousView) {
        map.setView(previousView.center, previousView.zoom);
        previousView = null;
    }
}

const shopMarkers = {};
const droneMarkers = {};
const routeLines = {};

const shopIcon = L.divIcon({
    className: "",
    html: '<div style="background:#4a80d4;color:#fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3)">S</div>',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
});

const droneIcon = L.divIcon({
    className: "",
    html: '<div style="background:#e53935;color:#fff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3)">&#9992;</div>',
    iconSize: [26, 26],
    iconAnchor: [13, 13],
});

const userIcon = L.divIcon({
    className: "",
    html: '<div style="background:#4285f4;width:14px;height:14px;border-radius:50%;border:3px solid #fff;box-shadow:0 0 0 2px #4285f4,0 1px 3px rgba(0,0,0,.3)"></div>',
    iconSize: [14, 14],
    iconAnchor: [7, 7],
});

async function loadShops() {
    const res = await fetch("/api/shops");
    shops = await res.json();

    const ul = document.getElementById("shops");
    shops.forEach((shop) => {
        const marker = L.marker([shop.lat, shop.lon], { icon: shopIcon })
            .addTo(map)
            .bindPopup(`<strong>${shop.name}</strong>`)
            .on("click", () => showShopItems(shop));
        shopMarkers[shop.shop_id] = marker;

        const li = document.createElement("li");
        li.textContent = shop.name;
        li.addEventListener("click", () => showShopItems(shop));
        ul.appendChild(li);
    });
}

async function loadOrders() {
    const res = await fetch("/api/orders");
    const orderList = await res.json();
    const ul = document.getElementById("order-list");
    const noOrders = document.getElementById("no-orders");
    ul.innerHTML = "";

    const currentIds = new Set(orderList.map((o) => o.order_id));
    for (const id of Object.keys(droneMarkers)) {
        if (!currentIds.has(id)) {
            map.removeLayer(droneMarkers[id]);
            map.removeLayer(routeLines[id]);
            delete droneMarkers[id];
            delete routeLines[id];
        }
    }

    if (orderList.length === 0) {
        noOrders.classList.remove("hidden");
        return;
    }

    noOrders.classList.add("hidden");
    orderList.forEach((o) => {
        const pos = [o.drone.location.lat, o.drone.location.lon];
        const shopPos = [o.shop_lat, o.shop_lon];

        if (droneMarkers[o.order_id]) {
            droneMarkers[o.order_id].setLatLng(pos);
            routeLines[o.order_id].setLatLngs([pos, shopPos]);
        } else {
            droneMarkers[o.order_id] = L.marker(pos, { icon: droneIcon })
                .addTo(map)
                .bindPopup(`Drone #${o.drone.drone_id} - ${o.item_name}`);
            routeLines[o.order_id] = L.polyline([pos, shopPos], {
                color: "#e53935",
                weight: 2,
                dashArray: "6,6",
            }).addTo(map);
        }

        const li = document.createElement("li");
        li.textContent = `${o.item_name} - ${o.shop_name} (${o.status})`;
        li.addEventListener("click", () => viewOrder(o.order_id));
        ul.appendChild(li);
    });
}

async function viewOrder(orderId) {
    const res = await fetch(`/api/orders/${orderId}`);
    if (!res.ok) return;
    currentOrder = await res.json();
    hide("shop-list");
    hide("shop-detail");
    show("order-status");
    renderStatus(currentOrder);
    const pos = [currentOrder.drone.location.lat, currentOrder.drone.location.lon];
    const shopPos = [currentOrder.shop_lat, currentOrder.shop_lon];
    map.fitBounds(L.latLngBounds(pos, shopPos), { padding: [50, 50] });
    startPolling();
}

function showShopItems(shop) {
    saveView();
    selectedShop = shop;
    hide("shop-list");
    hide("order-status");
    show("shop-detail");
    document.getElementById("shop-name").textContent = shop.name;

    const ul = document.getElementById("items");
    ul.innerHTML = "";
    shop.items.forEach((item) => {
        const li = document.createElement("li");
        li.innerHTML = `<span>${item.name}</span><button>Order</button>`;
        li.querySelector("button").addEventListener("click", () => placeOrder(shop.shop_id, item.item_id));
        ul.appendChild(li);
    });

    map.flyTo([shop.lat, shop.lon], 15);
}

async function placeOrder(shopId, itemId) {
    const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shop_id: shopId, item_id: itemId }),
    });

    if (!res.ok) {
        const err = await res.json();
        alert(err.error);
        return;
    }

    currentOrder = await res.json();
    loadOrders();
    hide("shop-detail");
    show("order-status");
    renderStatus(currentOrder);
    const pos = [currentOrder.drone.location.lat, currentOrder.drone.location.lon];
    const shopPos = [currentOrder.shop_lat, currentOrder.shop_lon];
    map.fitBounds(L.latLngBounds(pos, shopPos), { padding: [50, 50] });
    startPolling();
}

function renderStatus(order) {
    const d = order.drone;
    document.getElementById("status-content").innerHTML = `
        <div><strong>Order:</strong> ${order.order_id}</div>
        <div><strong>From:</strong> ${order.shop_name}</div>
        <div><strong>Item:</strong> ${order.item.name}</div>
        <div><strong>Status:</strong> ${order.status}</div>
        <div><strong>ETA:</strong> ${order.eta}</div>
        <div><strong>Drone:</strong> #${d.drone_id}</div>
        <div><strong>Battery:</strong> ${d.battery_level}%</div>
    `;
}

function startPolling() {
    stopPolling();
    pollTimer = setInterval(async () => {
        loadOrders();
        if (currentOrder) {
            const res = await fetch(`/api/orders/${currentOrder.order_id}`);
            if (!res.ok) return;
            currentOrder = await res.json();
            renderStatus(currentOrder);
        }
    }, 2000);
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

function resetView() {
    stopPolling();
    currentOrder = null;
    selectedShop = null;
    hide("order-status");
    hide("shop-detail");
    show("shop-list");
    restoreView();
}

document.getElementById("back-btn").addEventListener("click", () => {
    hide("shop-detail");
    show("shop-list");
    selectedShop = null;
    restoreView();
});

document.getElementById("new-order-btn").addEventListener("click", resetView);

let userMarker = null;

function onUserPosition(pos) {
    const latlng = [pos.coords.latitude, pos.coords.longitude];
    if (userMarker) {
        userMarker.setLatLng(latlng);
    } else {
        userMarker = L.marker(latlng, { icon: userIcon })
            .addTo(map)
            .bindPopup("You");
    }
}

if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
        onUserPosition,
        (err) => console.warn("Geolocation error:", err.message),
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

function show(id) {
    document.getElementById(id).classList.remove("hidden");
}

function hide(id) {
    document.getElementById(id).classList.add("hidden");
}

loadShops();
loadOrders();
