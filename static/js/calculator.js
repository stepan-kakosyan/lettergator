(function () {
	function initCalculator() {
		var modal = document.getElementById('calculator-modal');
		var closeBtn = document.getElementById('close-calculator-btn');
		var radioEmail = document.getElementById('calc-radio-email');
		var radioPhysical = document.getElementById('calc-radio-physical');
		var countrySelect = document.getElementById('calc-country');
		var filesSelect = document.getElementById('calc-pages');
		var photosSelect = document.getElementById('calc-photos');
		var totalPriceDisplay = document.getElementById('calc-total-price');
		var breakdownDisplay = document.getElementById('calc-breakdown');
		var physicalFields = document.getElementById('calc-physical-fields');
		var emailFields = document.getElementById('calc-email-fields');

		if (!modal) {
			return;
		}

		var countriesLoaded = false;

		function getYearsValue() {
			if (radioPhysical && radioPhysical.checked) {
				var sel = document.getElementById('calc-years-physical');
				return sel ? parseInt(sel.value || '0', 10) : 0;
			}
			var sel = document.getElementById('calc-years-email');
			return sel ? parseInt(sel.value || '0', 10) : 0;
		}

		function openModal() {
			modal.classList.remove('hidden');
			modal.classList.add('flex');
		}

		function closeModal() {
			modal.classList.add('hidden');
			modal.classList.remove('flex');
		}

		function getPricingConfig() {
			var form = document.getElementById('physical-letter-form');
			if (form) {
				   return {
					   extraPagePrice: parseFloat(
						   form.dataset.extraPagePrice || '0.50'
					   ),
					   extraPhotoPrice: parseFloat(
						   form.dataset.extraPhotoPrice || '1.00'
					   ),
					   extraYearPrice: parseFloat(
						   form.dataset.extraYearPrice || '0.50'
					   ),
				   };
			}
			return {
				extraPagePrice: 0.50,
				extraPhotoPrice: 1.00,
				extraYearPrice: 0.50,
			};
		}

		function getCountryBasePrice() {
			if (!countrySelect || !countrySelect.value) {
				return null;
			}
			// Try countries-pricing-data JSON first
			var node = document.getElementById('countries-pricing-data');
			if (node) {
				try {
					var data = JSON.parse(node.textContent);
					var entry = data[countrySelect.value];
					if (entry) {
						return parseFloat(entry.price || '0');
					}
				} catch (e) {
					// ignore
				}
			}
			// Fallback: parse from option text " ($X.XX)"
			var opt = countrySelect.options[countrySelect.selectedIndex];
			if (opt && opt.value) {
				var match = opt.textContent.match(/\(\$([0-9.]+)\)/);
				if (match) {
					return parseFloat(match[1]);
				}
			}
			return null;
		}

		function calculatePhysicalPrice() {
			var pricing = getPricingConfig();
			var base = getCountryBasePrice();
			if (base === null) {
				return {
					total: 0,
					breakdown: 'Select a country to see pricing.',
				};
			}

			var files = filesSelect
				? parseInt(filesSelect.value || '0', 10)
				: 0;
			var photos = photosSelect
				? parseInt(photosSelect.value || '0', 10)
				: 0;
			var years = getYearsValue();
			if (isNaN(files) || files < 0) { files = 0; }
			if (isNaN(photos) || photos < 0) { photos = 0; }
			if (isNaN(years) || years < 0) { years = 0; }

			var total = base;
			total += pricing.extraPagePrice * files;
			total += pricing.extraPhotoPrice * photos;
			total += pricing.extraYearPrice * years;

			var parts = ['Base $' + base.toFixed(2)];
			   if (files > 0) {
				   parts.push(
					   'pages(' + files + ') +$' +
					   (pricing.extraPagePrice * files).toFixed(2)
				   );
			   }
			if (photos > 0) {
				parts.push(
					'photos(' + photos + ') +$' +
					(pricing.extraPhotoPrice * photos).toFixed(2)
				);
			}
			if (years > 0) {
				parts.push(
					years + ' yr(s) +$' +
					(pricing.extraYearPrice * years).toFixed(2)
				);
			}

			return { total: total, breakdown: parts.join(' · ') };
		}

		function calculateEmailPrice() {
			var pricing = getPricingConfig();
			var years = getYearsValue();
			if (isNaN(years) || years < 0) { years = 0; }

			var total = pricing.extraYearPrice * years;
			var breakdown = years > 0
				? years + ' year(s) × $' +
				  pricing.extraYearPrice.toFixed(2) +
				  '/yr = $' +
				  total.toFixed(2)
				: 'Free — delivery under 1 year has no extra charge.';

			return { total: total, breakdown: breakdown };
		}

		function updateCalculation() {
			var isPhysical = radioPhysical && radioPhysical.checked;
			var result = isPhysical
				? calculatePhysicalPrice()
				: calculateEmailPrice();
			if (totalPriceDisplay) {
				totalPriceDisplay.textContent = '$' + result.total.toFixed(2);
			}
			if (breakdownDisplay) {
				breakdownDisplay.textContent = result.breakdown;
			}
		}

		function triggerHtmxCountriesLoad() {
			if (window.htmx) {
				htmx.trigger(document.body, 'calc-load-countries');
			}
		}

		function toggleFields() {
			var isPhysical = radioPhysical && radioPhysical.checked;
			if (physicalFields) {
				physicalFields.classList.toggle('hidden', !isPhysical);
			}
			if (emailFields) {
				emailFields.classList.toggle('hidden', isPhysical);
			}
			if (isPhysical && !countriesLoaded) {
				countriesLoaded = true;
				triggerHtmxCountriesLoad();
			}
			updateCalculation();
		}

		// Bind open buttons (support both id and class)
		document.querySelectorAll(
			'#open-calculator-btn, .open-calculator-btn'
		).forEach(function (btn) {
			btn.addEventListener('click', openModal);
		});

		if (closeBtn) {
			closeBtn.addEventListener('click', closeModal);
		}

		modal.addEventListener('click', function (e) {
			if (e.target === modal) { closeModal(); }
		});

		if (radioEmail) {
			radioEmail.addEventListener('change', toggleFields);
		}
		if (radioPhysical) {
			radioPhysical.addEventListener('change', toggleFields);
		}

		[countrySelect, filesSelect, photosSelect].forEach(function (el) {
			if (el) {
				el.addEventListener('change', updateCalculation);
			}
		});

		// Years selects are dynamically identified by class
		document.addEventListener('change', function (e) {
			if (e.target && e.target.classList.contains('calc-years')) {
				updateCalculation();
			}
		});

		// After HTMX swaps countries, recalculate
		document.body.addEventListener('htmx:afterSwap', function (e) {
			if (
				e.detail &&
				e.detail.target &&
				e.detail.target.id === 'calc-country'
			) {
				updateCalculation();
			}
		});

		toggleFields();
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', initCalculator);
	} else {
		initCalculator();
	}
})();
