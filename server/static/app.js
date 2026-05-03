const map = L.map("map").setView([63.4305, 10.3951], 13);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
}).addTo(map);

let shops = [];
let selectedShop = null;
let currentOrder = null;
let previousView = null;
let pendingOrder = null;

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
            delete droneMarkers[id];
        }
    }

    if (orderList.length === 0) {
        noOrders.classList.remove("hidden");
        return;
    }

    noOrders.classList.add("hidden");
    orderList.forEach((o) => {
        const pos = [o.drone.location.lat, o.drone.location.lon];

        if (droneMarkers[o.order_id]) {
            droneMarkers[o.order_id].setLatLng(pos);
        } else {
            droneMarkers[o.order_id] = L.marker(pos, { icon: droneIcon })
                .addTo(map)
                .bindPopup(`Drone #${o.drone.drone_id} - ${o.item_name}`);
        }

        const li = document.createElement("li");
        li.textContent = `${o.item_name} - ${o.shop_name} (${o.status})`;
        li.addEventListener("click", () => viewOrder(o.order_id));
        ul.appendChild(li);
    });
}

async function viewOrder(orderId) {
    currentOrder = await fetchOrder(orderId);
    if (!currentOrder) return;
    hide("shop-list");
    hide("shop-detail");
    show("order-status");
    renderStatus(currentOrder);
    const pos = [currentOrder.drone.location.lat, currentOrder.drone.location.lon];
    const shopPos = [currentOrder.shop_lat, currentOrder.shop_lon];
    map.fitBounds(L.latLngBounds(pos, shopPos), { padding: [50, 50] });
}

async function fetchOrder(orderId) {
    const res = await fetch(`/api/orders/${orderId}`);
    if (!res.ok) return null;
    return res.json();
}

async function refreshCurrentOrder() {
    if (!currentOrder) return;
    const updated = await fetchOrder(currentOrder.order_id);
    if (!updated) return;
    currentOrder = updated;
    if (!document.getElementById("order-status").classList.contains("hidden")) {
        renderStatus(currentOrder);
    }
    const d = currentOrder.drone;
    if (droneMarkers[currentOrder.order_id]) {
        droneMarkers[currentOrder.order_id].setLatLng([d.location.lat, d.location.lon]);
    }
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
        li.querySelector("button").addEventListener("click", () => showConfirm(shop, item));
        ul.appendChild(li);
    });

    map.flyTo([shop.lat, shop.lon], 15);
}

function showConfirm(shop, item) {
    pendingOrder = { shop, item };
    document.getElementById("confirm-item").textContent =
        `${item.name} from ${shop.name}`;
    document.querySelector('input[name="priority"][value="standard"]').checked = true;
    show("confirm-overlay");
}

document.getElementById("confirm-cancel").addEventListener("click", () => {
    pendingOrder = null;
    hide("confirm-overlay");
});

document.getElementById("confirm-submit").addEventListener("click", () => {
    if (!pendingOrder) return;
    const priority = document.querySelector('input[name="priority"]:checked').value;
    const { shop, item } = pendingOrder;
    pendingOrder = null;
    hide("confirm-overlay");
    placeOrder(shop.shop_id, item.item_id, priority);
});

async function placeOrder(shopId, itemId, priority) {
    const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shop_id: shopId, item_id: itemId, priority, lat: userLatLng[0], lon: userLatLng[1] }),
    });

    if (!res.ok) {
        const err = await res.json();
        alert(err.error);
        return;
    }

    currentOrder = await res.json();
    await loadOrders();
    hide("shop-detail");
    show("order-status");
    renderStatus(currentOrder);
    const pos = [currentOrder.drone.location.lat, currentOrder.drone.location.lon];
    const shopPos = [currentOrder.shop_lat, currentOrder.shop_lon];
    map.fitBounds(L.latLngBounds(pos, shopPos), { padding: [50, 50] });
}

function renderStatus(order) {
    const d = order.drone;
    document.getElementById("status-content").innerHTML = `
        <div><strong>Order:</strong> ${order.order_id}</div>
        <div><strong>From:</strong> ${order.shop_name}</div>
        <div><strong>Item:</strong> ${order.item.name}</div>
        <div><strong>Status:</strong> ${order.status}</div>
        <div><strong>Priority:</strong> ${order.priority === "express" ? "Express" : "Standard"}</div>
        <div><strong>Drone:</strong> #${d.drone_id}</div>
        <div><strong>Battery:</strong> ${Math.round(d.battery_level)}%</div>
    `;
}

function resetView() {
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
let userLatLng = null;

function createUserMarker(latlng) {
    if (userMarker) {
        userMarker.setLatLng(latlng);
    } else {
        userMarker = L.marker(latlng, { icon: userIcon, draggable: true })
            .addTo(map)
            .bindPopup("You (drag to move)");
        userMarker.on("dragend", () => {
            const pos = userMarker.getLatLng();
            userLatLng = [pos.lat, pos.lng];
        });
    }
    userLatLng = latlng;
}

function onUserPosition(pos) {
    createUserMarker([pos.coords.latitude, pos.coords.longitude]);
}

if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
        onUserPosition,
        () => { if (!userLatLng) createUserMarker([map.getCenter().lat, map.getCenter().lng]); },
        { enableHighAccuracy: true, timeout: 10000 }
    );
} else {
    createUserMarker([map.getCenter().lat, map.getCenter().lng]);}

document.getElementById("locate-btn").addEventListener("click", () => {
    if (userLatLng) map.flyTo(userLatLng, 15);
});

function show(id) {
    document.getElementById(id).classList.remove("hidden");
}

function hide(id) {
    document.getElementById(id).classList.add("hidden");
}

loadShops();
loadOrders();
setInterval(() => {
    loadOrders();
    refreshCurrentOrder();
}, 2000);
