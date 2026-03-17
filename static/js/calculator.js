// Live Carbon Footprint Calculator Preview
// Updates CO2 values in real-time as user fills the form

const EMISSION_FACTORS = {
  transport: { car: 0.21, bus: 0.089, train: 0.041, bike: 0.0, flight: 0.255 },
  food: { meat_heavy: 7.19, meat_medium: 4.67, vegetarian: 3.81, vegan: 2.89 },
  energy: { electricity: 0.82, lpg: 2.98 },
  shopping: 0.5,
};

function updatePreview() {
  // Transport
  const mode = document.getElementById('transport_mode').value;
  const km   = parseFloat(document.getElementById('transport_km').value) || 0;
  const transportCO2 = km * (EMISSION_FACTORS.transport[mode] || 0.21);

  // Food
  const foodType = document.querySelector('input[name="food_type"]:checked')?.value || 'meat_medium';
  const foodCO2  = EMISSION_FACTORS.food[foodType] || 4.67;

  // Energy
  const elec    = parseFloat(document.getElementById('electricity_kwh').value) || 0;
  const lpg     = parseFloat(document.getElementById('lpg_kg').value) || 0;
  const energyCO2 = (elec * EMISSION_FACTORS.energy.electricity) + (lpg * EMISSION_FACTORS.energy.lpg);

  // Shopping
  const spend      = parseFloat(document.getElementById('shopping_spend').value) || 0;
  const shoppingCO2 = (spend / 100) * EMISSION_FACTORS.shopping;

  const total = transportCO2 + foodCO2 + energyCO2 + shoppingCO2;

  // Update display
  document.getElementById('prev-transport').textContent = transportCO2.toFixed(2);
  document.getElementById('prev-food').textContent      = foodCO2.toFixed(2);
  document.getElementById('prev-energy').textContent    = energyCO2.toFixed(2);
  document.getElementById('prev-shopping').textContent  = shoppingCO2.toFixed(2);
  document.getElementById('total-preview').textContent  = total.toFixed(2) + ' kg CO₂';

  // Color the total
  const totalEl = document.getElementById('total-preview');
  if (total < 5)       totalEl.style.color = '#2d9e5f';
  else if (total < 10) totalEl.style.color = '#f4a261';
  else                 totalEl.style.color = '#e63946';
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', updatePreview);
