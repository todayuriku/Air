function switchTab(t, e) {
    document.querySelectorAll('.tab-content').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.getElementById(t + '-view').classList.add('active');
    e.classList.add('active');
    document.getElementById('reg-form').style.visibility = (t === 'fridge') ? 'visible' : 'hidden';
    
    document.getElementById('category-tabs').style.display = (t === 'fridge') ? 'flex' : 'none';
}

function filterCategory(cat, btn) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.food-item').forEach(item => {
        item.style.display = (cat === 'all' || item.getAttribute('data-category') === cat) ? 'flex' : 'none';
    });
}

const masterFoodList = Object.keys(unitMap);

const yomiDict = {
    "豚肉": "ぶたにく", "牛肉": "ぎゅうにく", "鶏肉": "とりにく", "ひき肉": "ひきにく", "挽肉": "ひきにく", "豚バラ": "ぶたばら",
    "人参": "にんじん", "玉ねぎ": "たまねぎ", "大根": "だいこん", "白菜": "はくさい", "長ねぎ": "ながねぎ", "玉葱": "たまねぎ",
    "茄子": "なす", "胡瓜": "きゅうり", "じゃが芋": "じゃがいも", "生姜": "しょうが", "大蒜": "にんにく",
    "卵": "たまご", "玉子": "たまご", "牛乳": "ぎゅうにゅう", "豆乳": "とうにゅう",
    "豆腐": "とうふ", "納豆": "なっとう", "油揚げ": "あぶらあげ", "厚揚げ": "あつあげ",
    "鮭": "さけ", "鯖": "さば", "鯵": "あじ", "鮪": "まぐろ", "鰤": "ぶり",
    "米": "こめ", "ご飯": "ごはん", "食パン": "しょくぱん",
    "醤油": "しょうゆ", "砂糖": "さとう", "塩": "しお", "酢": "す", "味噌": "みそ", "油": "あぶら", "胡麻油": "ごまあぶら",
    "水": "みず", "お茶": "おちゃ", "麦茶": "むぎちゃ"
};

const categoryOrder = {
    "乳・卵": 1,
    "肉類": 2,
    "魚介類": 3,
    "大豆製品": 4,
    "加工食品": 5,
    "野菜": 6,
    "その他": 7,
    "飲料": 8,
    "調味料": 9
};

function hiraToKata(str) {
    return str.replace(/[\u3041-\u3096]/g, function(match) {
        return String.fromCharCode(match.charCodeAt(0) + 0x60);
    });
}

function sortFridge(criteria, btn) {
    document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const container = document.getElementById('fridge-items-container');
    const items = Array.from(container.querySelectorAll('.food-item'));

    items.sort((a, b) => {
        if (criteria === 'exp_asc') {
            return a.dataset.exp.localeCompare(b.dataset.exp);
        } else if (criteria === 'newest') {
            return parseInt(b.dataset.order) - parseInt(a.dataset.order);
        } else if (criteria === 'oldest') {
            return parseInt(a.dataset.order) - parseInt(b.dataset.order);
        } else if (criteria === 'name_asc') {
            const yomiA = yomiDict[a.dataset.name] || a.dataset.name;
            const yomiB = yomiDict[b.dataset.name] || b.dataset.name;
            return yomiA.localeCompare(yomiB, 'ja');
        } else if (criteria === 'cat_asc') {
            const orderA = categoryOrder[a.dataset.category] || 99;
            const orderB = categoryOrder[b.dataset.category] || 99;
            return orderA - orderB;
        }
    });

    items.forEach(item => container.appendChild(item));
}

const nameInput = document.getElementById('item_name_input');
const suggestList = document.getElementById('suggest-list');
const unitDisplay = document.getElementById('unit-display');

nameInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    suggestList.innerHTML = '';
    unitDisplay.textContent = unitMap[val] || '個';

    if (val.length === 0) {
        suggestList.style.display = 'none';
        return;
    }

    const kataVal = hiraToKata(val);

    const matched = masterFoodList.filter(food => {
        if (food.includes(val) || food.includes(kataVal)) return true;
        const yomi = yomiDict[food];
        if (yomi && yomi.includes(val)) return true;
        return false;
    });
    
    if (matched.length > 0) {
        matched.forEach(food => {
            const div = document.createElement('div');
            div.className = 'suggest-item';
            div.textContent = food;
            div.onclick = () => {
                nameInput.value = food;
                unitDisplay.textContent = unitMap[food] || '個';
                suggestList.style.display = 'none';
            };
            suggestList.appendChild(div);
        });
        suggestList.style.display = 'block';
    } else {
        suggestList.style.display = 'none';
    }
});

document.addEventListener('click', (e) => {
    if (e.target !== nameInput && e.target.parentNode !== suggestList) {
        suggestList.style.display = 'none';
    }
});

function openConsumeModal(name, maxQty, unit) {
    document.getElementById('modal-item-name').textContent = name;
    document.getElementById('modal-max-qty').textContent = maxQty;
    document.getElementById('modal-unit').textContent = unit;
    document.getElementById('modal-input-name').value = name;
    const inputAmount = document.getElementById('modal-input-amount');
    inputAmount.max = maxQty;
    inputAmount.value = maxQty;
    if (unit === 'g') { inputAmount.min = '1'; inputAmount.step = '1'; } 
    else { inputAmount.min = '0.1'; inputAmount.step = '0.1'; }
    document.getElementById('consume-modal').style.display = 'flex';
}

function closeConsumeModal() { document.getElementById('consume-modal').style.display = 'none'; }

function openManualExpenseModal() {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    document.getElementById('expense_date_input').value = `${yyyy}-${mm}-${dd}`;
    document.getElementById('manual-expense-modal').style.display = 'flex';
}

async function handleReceiptUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    document.getElementById('scan-loading').style.display = 'block';
    document.getElementById('scan-preview-area').style.display = 'none';

    const formData = new FormData();
    formData.append('receipt_image', file);

    try {
        const response = await fetch('/scan_receipt', { method: 'POST', body: formData });
        const data = await response.json();
        
        if (data.error) {
            alert(data.error);
        } else {
            renderScanPreview(data.items);
        }
    } catch (error) {
        alert("通信エラーが発生しました。");
    } finally {
        document.getElementById('scan-loading').style.display = 'none';
        event.target.value = '';
    }
}

function renderScanPreview(items) {
    const listArea = document.getElementById('scan-items-list');
    listArea.innerHTML = '';

    if (items.length === 0) {
        listArea.innerHTML = '<p style="text-align:center; color:#999;">食品が見つかりませんでした。</p>';
        document.getElementById('scan-preview-area').style.display = 'block';
        return;
    }

    items.forEach((item, index) => {
        const row = document.createElement('div');
        row.className = 'scan-item-row';
        
        row.innerHTML = `
            <input type="text" class="scan-input-name" value="${item.name}" placeholder="食材名">
            <div class="scan-detail-row">
                <div style="font-size:12px; color:#555;">数量: <input type="number" class="scan-input-num scan-qty" value="${item.quantity}" min="0.1" step="0.1"> <span class="scan-unit" style="font-weight:bold; color:var(--main-blue);">${item.unit}</span></div>
                <div style="font-size:12px; color:#555;">金額: <input type="number" class="scan-input-num scan-price" value="${item.price}" min="0"> 円</div>
                <button type="button" onclick="this.parentElement.parentElement.remove()" style="background:#FFEBEE; color:#C62828; border:none; border-radius:50%; width:24px; height:24px; font-weight:bold; cursor:pointer;">×</button>
            </div>
            <div style="font-size:11px; color:#666; margin-top:6px; display:flex; align-items:center; gap:5px;">
                備考: <input type="text" class="scan-input-memo" value="${item.memo || ''}" placeholder="（例：レシート上の項目名）" style="flex:1; padding:4px; border-radius:5px; border:1px solid #ccc; font-size:11px; outline:none;">
            </div>
        `;
        
        const nameInput = row.querySelector('.scan-input-name');
        const unitSpan = row.querySelector('.scan-unit');
        nameInput.addEventListener('input', (e) => {
            unitSpan.textContent = unitMap[e.target.value] || '個';
        });

        listArea.appendChild(row);
    });

    document.getElementById('scan-preview-area').style.display = 'block';
}

async function submitReceiptItems() {
    const rows = document.querySelectorAll('.scan-item-row');
    const itemsToAdd = [];

    rows.forEach(row => {
        const name = row.querySelector('.scan-input-name').value;
        const qty = row.querySelector('.scan-qty').value;
        const price = row.querySelector('.scan-price').value || 0;
        const memo = row.querySelector('.scan-input-memo').value || ""; 

        if (name && qty > 0) {
            itemsToAdd.push({ name: name, quantity: qty, price: price, memo: memo });
        }
    });

    if (itemsToAdd.length === 0) {
        alert("登録する食材がありません。");
        return;
    }

    try {
        const response = await fetch('/add_multiple', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: itemsToAdd })
        });
        
        if (response.ok) {
            alert("冷蔵庫に登録しました！");
            window.location.reload(); 
        } else {
            alert("登録に失敗しました。");
        }
    } catch (error) {
        alert("通信エラーが発生しました。");
    }
}

async function getAiRecommendation() {
    const responseArea = document.getElementById('ai-response-area');
    
    responseArea.innerHTML = `
        <div style="text-align:center; padding: 20px;">
            <div class="dot-spinner"></div>
            <span style="color: var(--main-blue); font-weight: bold; font-size: 12px; display: inline-block;">AIシェフが献立を考案中...</span>
        </div>
    `;

    const mode = document.querySelector('input[name="ai_mode"]:checked').value;
    const time = document.querySelector('input[name="ai_time"]:checked').value;
    const prioritize = document.getElementById('ai_prioritize').checked;

    try {
        const response = await fetch('/ask_ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode, time: time, prioritize: prioritize })
        });
        
        const data = await response.json();
        let formattedAnswer = data.answer.replace(/\n/g, '<br>');
        let linksHtml = '';
        if (data.links && data.links.length > 0) {
            linksHtml = '<div style="margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 10px;">';
            data.links.forEach(link => {
                linksHtml += `<a target="_blank" href="${link.url}" class="recipe-link">検索：「${link.name}」のレシピ</a>`;
            });
            linksHtml += '</div>';
        }
        responseArea.innerHTML = formattedAnswer + linksHtml;
    } catch (error) {
        responseArea.innerHTML = '<span style="color: #C62828; font-weight: bold;">通信エラーが発生しました。</span>';
    }
}

async function updateExpenseChart() {
    const period = document.getElementById('expense-period').value;
    const area = document.getElementById('expense-chart-area');
    area.innerHTML = `<p style="font-size:12px; color:#888;">読み込み中...</p>`;
    try {
        const res = await fetch(`/api/get_chart/${period}`);
        const data = await res.json();
        if (data.chart) {
            area.innerHTML = `<img src="data:image/png;base64,${data.chart}" style="width: 100%; height: auto; border-radius: 8px;">`;
        } else {
            area.innerHTML = `<p style="font-size: 12px; color: #666; text-align: center;">レシートの登録データがありません。</p>`;
        }
    } catch {
        area.innerHTML = `<p style="font-size: 12px; color: red;">通信エラーが発生しました。</p>`;
    }
}

async function updateRankingChart() {
    const period = document.getElementById('ranking-period').value;
    const area = document.getElementById('ranking-chart-area');
    area.innerHTML = `<p style="font-size:12px; color:#888; text-align:center;">読み込み中...</p>`;
    try {
        const res = await fetch(`/api/get_ranking_chart/${period}`);
        const data = await res.json();
        let html = '';
        if (data.g) html += `<img src="data:image/png;base64,${data.g}" style="width: 100%; height: auto; margin-bottom: 15px; border-radius: 8px;">`;
        if (data.pack) html += `<img src="data:image/png;base64,${data.pack}" style="width: 100%; height: auto; margin-bottom: 15px; border-radius: 8px;">`;
        if (data.other) html += `<img src="data:image/png;base64,${data.other}" style="width: 100%; height: auto; border-radius: 8px;">`;
        if (html === '') {
            html = `<p style="font-size: 12px; color: #666; text-align: center;">消費データがありません。</p>`;
        }
        area.innerHTML = html;
    } catch {
        area.innerHTML = `<p style="font-size: 12px; color: red; text-align: center;">通信エラーが発生しました。</p>`;
    }
}

function addManualScanRow() {
    const listArea = document.getElementById('scan-items-list');
    const row = document.createElement('div');
    row.className = 'scan-item-row';
    
    row.innerHTML = `
        <input type="text" class="scan-input-name" value="" placeholder="食材名">
        <div class="scan-detail-row">
            <div style="font-size:12px; color:#555;">数量: <input type="number" class="scan-input-num scan-qty" value="1" min="0.1" step="0.1"> <span class="scan-unit" style="font-weight:bold; color:var(--main-blue);">個</span></div>
            <div style="font-size:12px; color:#555;">金額: <input type="number" class="scan-input-num scan-price" value="0" min="0"> 円</div>
            <button type="button" onclick="this.parentElement.parentElement.remove()" style="background:#FFEBEE; color:#C62828; border:none; border-radius:50%; width:24px; height:24px; font-weight:bold; cursor:pointer;">×</button>
        </div>
        <div style="font-size:11px; color:#666; margin-top:6px; display:flex; align-items:center; gap:5px;">
            備考: <input type="text" class="scan-input-memo" value="" placeholder="（例：手動追加）" style="flex:1; padding:4px; border-radius:5px; border:1px solid #ccc; font-size:11px; outline:none;">
        </div>
    `;
    
    const nameInput = row.querySelector('.scan-input-name');
    const unitSpan = row.querySelector('.scan-unit');
    nameInput.addEventListener('input', (e) => {
        unitSpan.textContent = unitMap[e.target.value] || '個';
    });

    listArea.appendChild(row);
}