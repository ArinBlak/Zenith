// Text-to-Trade JavaScript Functions
// Add this script to your index.html before the closing </script> tag

let parsedCommand = null;

function fillCommand(text) {
    document.getElementById('trade-command').value = text;
}

async function parseCommand() {
    const input = document.getElementById('trade-command');
    const parseBtn = document.getElementById('parse-btn');
    const command = input.value.trim();

    if (!command) {
        alert('Please enter a trading command');
        return;
    }

    // Show loading state
    parseBtn.disabled = true;
    parseBtn.innerHTML = 'Parsing<span class=\"loading-spinner\"></span>';

    try {
        const response = await fetch('/parse-command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });

        const result = await response.json();
        parsedCommand = result;

        if (result.error || !result.intent) {
            showError(result.error || 'Failed to parse command');
        } else if (result.validation && !result.validation.valid) {
            showError('Validation errors: ' + result.validation.errors.join(', '));
        } else {
            showPreview(result);
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    } finally {
        parseBtn.disabled = false;
        parseBtn.innerHTML = 'Parse';
    }
}

function showPreview(result) {
    const preview = document.getElementById('parsed-preview');
    const strategyEl = document.getElementById('preview-strategy');
    const confidenceEl = document.getElementById('preview-confidence');
    const paramsEl = document.getElementById('preview-params');
    const errorEl = document.getElementById('preview-error');

    // Clear previous error
    errorEl.style.display = 'none';

    // Set strategy name
    const strategyNames = {
        'twap': '🎯 TWAP Strategy',
        'grid': '📊 Grid Trading',
        'market': '⚡ Market Order'
    };
    strategyEl.textContent = strategyNames[result.intent] || result.intent.toUpperCase();

    // Set confidence
    const confidence = Math.round(result.confidence * 100);
    confidenceEl.textContent = `${confidence}% Confidence`;

    // Build parameter cards
    const params = result.parameters;
    paramsEl.innerHTML = '';

    // Helper to add param card
    const addParam = (label, value) => {
        const card = document.createElement('div');
        card.className = 'param-card';
        card.innerHTML = `
            <div class="param-label">${label}</div>
            <div class="param-value">${value}</div>
        `;
        paramsEl.appendChild(card);
    };

    // Show relevant parameters
    if (params.symbol) addParam('Symbol', params.symbol);
    if (params.side) addParam('Side', params.side);
    if (params.quantity) addParam('Quantity', params.quantity);

    if (result.intent === 'twap') {
        if (params.duration_seconds) {
            const mins = Math.round(params.duration_seconds / 60);
            addParam('Duration', `${mins} minutes`);
        }
        if (params.num_orders) addParam('Orders', params.num_orders);
    } else if (result.intent === 'grid') {
        if (params.lower_price) addParam('Lower Price', `$${params.lower_price}`);
        if (params.upper_price) addParam('Upper Price', `$${params.upper_price}`);
        if (params.grids) addParam('Grid Levels', params.grids);
        if (params.quantity_per_grid) addParam('Qty/Grid', params.quantity_per_grid);
    }

    // Show conditions if any
    if (params.conditions) {
        const cond = params.conditions;
        if (cond.rsi_below) addParam('RSI Condition', `< ${cond.rsi_below}`);
        if (cond.rsi_above) addParam('RSI Condition', `> ${cond.rsi_above}`);
        if (cond.sentiment_above) addParam('Sentiment', `> ${cond.sentiment_above}`);
        if (cond.sentiment_below) addParam('Sentiment', `< ${cond.sentiment_below}`);
        if (cond.pause_on_bearish) addParam('Pause Mode', 'On Bearish');
    }

    // Show preview
    preview.style.display = 'block';
}

function showError(message) {
    const preview = document.getElementById('parsed-preview');
    const errorEl = document.getElementById('preview-error');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
    preview.style.display = 'block';
}

async function executeStrategy() {
    if (!parsedCommand || !parsedCommand.intent) {
        alert('No parsed command to execute');
        return;
    }

    if (!confirm('Execute this trading strategy?')) {
        return;
    }

    try {
        const response = await fetch('/execute-strategy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                intent: parsedCommand.intent,
                parameters: parsedCommand.parameters
            })
        });

        const result = await response.json();

        if (result.status === 'conditions_not_met') {
            alert('Conditions not met: ' + result.message + '\\n' + JSON.stringify(result.details, null, 2));
        } else if (result.error) {
            alert('Error: ' + result.error);
        } else {
            alert('Success: ' + result.message);
            cancelCommand(); // Clear the form
            addLog(`[${new Date().toLocaleTimeString()}] Strategy executed: ${result.message}`, "info");
        }
    } catch (error) {
        alert('Network error: ' + error.message);
    }
}

function cancelCommand() {
    document.getElementById('parsed-preview').style.display = 'none';
    document.getElementById('trade-command').value = '';
    parsedCommand = null;
}

// Allow Enter key to parse command
document.addEventListener('DOMContentLoaded', () => {
    const commandInput = document.getElementById('trade-command');
    if (commandInput) {
        commandInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                parseCommand();
            }
        });
    }
});
