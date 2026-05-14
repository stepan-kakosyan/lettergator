(function () {
	var form = document.getElementById('physical-letter-form');
	if (!form) {
		return;
	}

	// --- Inject existing attachments into preview areas ---
	var existingAttachments = [];
	var existingAttachmentsJSON = document.getElementById('physical-letter-existing-attachments');
	if (existingAttachmentsJSON) {
		try {
			existingAttachments = JSON.parse(existingAttachmentsJSON.textContent);
		} catch (err) {
			console.error('Failed to parse existing attachments:', err);
			existingAttachments = [];
		}
	}

	// Helper to render existing attachments in preview
	function renderExistingAttachments() {
		// Text files
		var textPreview = document.getElementById('text-preview');
		var photoPreview = document.getElementById('photo-preview');
		if (!textPreview || !photoPreview) return;

		// Remove any previous existing file rows
		var oldExisting = document.querySelectorAll('.existing-attachment-row');
		oldExisting.forEach(function(el) { el.remove(); });

		existingAttachments.forEach(function(att) {
			if (att.type === 'text') {
				var row = document.createElement('div');
				row.className = 'upload-file-row existing-attachment-row';
				var badge = document.createElement('span');
				badge.className = 'upload-file-badge';
				badge.textContent = att.name.split('.').pop().toUpperCase();
				var name = document.createElement('span');
				name.className = 'upload-file-name';
				name.textContent = att.name;
				var link = document.createElement('a');
				link.href = '#';
				link.target = '_blank';
				link.rel = 'noopener noreferrer';
				link.textContent = 'View';
				link.className = 'upload-file-view-link';
				link.addEventListener('click', function(e) {
					e.preventDefault();
					fetch(att.url)
						.then(resp => resp.json())
						.then(data => {
							if (data.url) {
								window.open(data.url, '_blank');
							}
						});
				});
				var removeBtn = document.createElement('button');
				removeBtn.type = 'button';
				removeBtn.className = 'upload-item-remove';
				removeBtn.textContent = 'Delete';
				removeBtn.addEventListener('click', function() {
					var input = document.createElement('input');
					input.type = 'hidden';
					input.name = 'delete_attachment_ids';
					input.value = att.id;
					form.appendChild(input);
					row.remove();
					existingAttachments = existingAttachments.filter(function(a) { return a.id !== att.id; });
					onInputsChanged();
				});
				row.appendChild(badge);
				row.appendChild(name);
				row.appendChild(link);
				row.appendChild(removeBtn);
				textPreview.appendChild(row);
			} else if (att.type === 'photo') {
				var wrapper = document.createElement('div');
				wrapper.className = 'upload-photo-card existing-attachment-row';
				var image = document.createElement('img');
				image.className = 'upload-photo-thumb';
				image.alt = att.name;
				image.src = '';
				// Fetch presigned URL and set as src
				fetch(att.url)
					.then(resp => resp.json())
					.then(data => {
						if (data.url) {
							image.src = data.url;
						}
					});
				var meta = document.createElement('p');
				meta.className = 'upload-photo-meta';
				meta.textContent = att.name;
				var removeBtn = document.createElement('button');
				removeBtn.type = 'button';
				removeBtn.className = 'upload-photo-remove';
				removeBtn.textContent = 'x';
				removeBtn.setAttribute('aria-label', 'Delete image ' + att.name);
				removeBtn.addEventListener('click', function() {
					var input = document.createElement('input');
					input.type = 'hidden';
					input.name = 'delete_attachment_ids';
					input.value = att.id;
					form.appendChild(input);
					wrapper.remove();
					existingAttachments = existingAttachments.filter(function(a) { return a.id !== att.id; });
					onInputsChanged();
				});
				wrapper.appendChild(image);
				wrapper.appendChild(removeBtn);
				wrapper.appendChild(meta);
				photoPreview.appendChild(wrapper);
			}
		});
	}


	var countryField = document.getElementById('id_country');
	var deliveryDateField = document.getElementById('id_requested_delivery_date');
	var messageField = document.getElementById('id_message_text');
	var textFilesField = document.getElementById('id_text_files');
	var photoFilesField = document.getElementById('id_photo_files');
	var textPreview = document.getElementById('text-preview');
	var photoPreview = document.getElementById('photo-preview');
	var totalPriceNode = document.getElementById('total-price');
	var breakdownNode = document.getElementById('pricing-breakdown');
	var errorNode = document.getElementById('client-errors');
	var payNowButton = document.getElementById('pay-now-btn');
	var saveDraftButton = document.getElementById('save-draft-btn');
	var submitActionField = document.getElementById('id_submit_action');
	var isPaidEditMode = form.dataset.isPaidEdit === '1';
	var originalTotalPrice = parseFloat(form.dataset.originalTotalPrice || '0');
	var currentBalance = parseFloat(form.dataset.userBalance || '0');
	var paidEditConfirmModal = document.getElementById('paid-edit-confirm-modal');
	var paidEditConfirmText = document.getElementById('paid-edit-confirm-text');
	var paidEditConfirmBtn = document.getElementById('paid-edit-confirm-btn');
	var paidEditCancelBtn = document.getElementById('paid-edit-cancel-btn');
	var paidEditBalanceModal = document.getElementById('paid-edit-balance-modal');
	var paidEditBalanceText = document.getElementById('paid-edit-balance-text');
	var paidEditBalanceCloseBtn = document.getElementById('paid-edit-balance-close-btn');
	var totalPrintablePagesField = document.getElementById('id_total_printable_pages');
	var printablePagesSection = document.getElementById('printable-pages-section');
	var suggestedPagesHint = document.getElementById('suggested-pages-hint');
	var textDropzone = document.getElementById('text-dropzone');
	var photoDropzone = document.getElementById('photo-dropzone');
	var existingAttachmentDeleteCheckboxes = Array.from(
		document.querySelectorAll('.existing-attachment-delete')
	);
	var selectedTextFiles = [];
	var selectedPhotoFiles = [];

	function debugLog(label, payload) {
		console.debug('[PhysicalLetter]', label, payload || {});
	}

	var countries = {};
	var countriesDataNode = document.getElementById('countries-pricing-data');
	try {
		countries = JSON.parse(
			countriesDataNode ? countriesDataNode.textContent : '{}'
		);
	} catch (err) {
		countries = {};
		debugLog('Countries parse failed', { error: String(err) });
	}
	var maxTextFiles = parseInt(form.dataset.maxTextFiles || '3', 10);
	var maxPhotoFiles = parseInt(form.dataset.maxPhotoFiles || '3', 10);
	var maxFileSizeMb = parseInt(form.dataset.maxFileSizeMb || '10', 10);
	var maxDeliveryYears = parseInt(form.dataset.maxDeliveryYears || '10', 10);
	var extraPhotoPrice = parseFloat(form.dataset.extraPhotoPrice || '1.0');
	var extraPagePrice = parseFloat(form.dataset.extraPagePrice || '0.5');
	var extraYearPrice = parseFloat(form.dataset.extraYearPrice || '0.5');
	var suggestedFilesLabel = (
		form.dataset.suggestedFilesLabel || 'Suggested from files'
	);
	var existingTextFilesCount = parseInt(
		form.dataset.existingTextFilesCount || '0',
		10
	);
	var existingPhotoFilesCount = parseInt(
		form.dataset.existingPhotoFilesCount || '0',
		10
	);
	if (isNaN(existingTextFilesCount) || existingTextFilesCount < 0) {
		existingTextFilesCount = 0;
	}
	if (isNaN(existingPhotoFilesCount) || existingPhotoFilesCount < 0) {
		existingPhotoFilesCount = 0;
	}
	var textExts = ['.pdf', '.txt', '.docx'];
	var photoExts = ['.jpg', '.jpeg', '.png'];
	debugLog('Init state', {
		countryValue: countryField.value,
		countriesKeys: Object.keys(countries),
		existingTextFilesCount: existingTextFilesCount,
		existingPhotoFilesCount: existingPhotoFilesCount,
		action: submitActionField ? submitActionField.value : '(missing)',
	});

	function clearErrors() {
		errorNode.classList.add('hidden');
		errorNode.innerHTML = '';
		if (payNowButton) {
			payNowButton.disabled = false;
			payNowButton.classList.remove('opacity-60', 'cursor-not-allowed');
		}
	}

	function setErrors(items) {
		if (!items.length) {
			clearErrors();
			return;
		}
		errorNode.innerHTML = items.map(function (msg) {
			return '<p>' + msg + '</p>';
		}).join('');
		errorNode.classList.remove('hidden');
		if (payNowButton) {
			payNowButton.disabled = true;
			payNowButton.classList.add('opacity-60', 'cursor-not-allowed');
		}
	}

	function ext(name) {
		var idx = name.lastIndexOf('.');
		if (idx < 0) {
			return '';
		}
		return name.slice(idx).toLowerCase();
	}

	function formatBytes(bytes) {
		if (bytes < 1024 * 1024) {
			return (bytes / 1024).toFixed(0) + 'KB';
		}
		return (bytes / (1024 * 1024)).toFixed(2) + 'MB';
	}

	function extensionBadge(extension) {
		if (extension === '.pdf') {
			return 'PDF';
		}
		if (extension === '.docx') {
			return 'DOCX';
		}
		if (extension === '.txt') {
			return 'TXT';
		}
		if (extension === '.jpg' || extension === '.jpeg') {
			return 'JPG';
		}
		if (extension === '.png') {
			return 'PNG';
		}
		return 'FILE';
	}

	function suggestedPages() {
		return currentExistingTextFilesCount() + selectedTextFiles.length;
	}

	function currentExistingTextFilesCount() {
		return existingAttachments.filter(function (attachment) {
			return attachment.type === 'text';
		}).length;
	}

	function currentExistingPhotoFilesCount() {
		return existingAttachments.filter(function (attachment) {
			return attachment.type === 'photo';
		}).length;
	}

	function syncPrintablePagesState() {
		if (!totalPrintablePagesField || !printablePagesSection) {
			return;
		}

		var minPagesFromFiles = currentExistingTextFilesCount() + selectedTextFiles.length;
		var minPhotosFromFiles = currentExistingPhotoFilesCount() + selectedPhotoFiles.length;
		var currentPages = parseInt(totalPrintablePagesField.value || '0', 10);
		if (isNaN(currentPages) || currentPages < 0) {
			currentPages = 0;
		}

		// If there are no files or photos at all, hide section and set to 0
		if (minPagesFromFiles === 0 && minPhotosFromFiles === 0) {
			printablePagesSection.classList.add('hidden');
			totalPrintablePagesField.value = '0';
			return;
		}

		if (minPagesFromFiles > 0) {
			printablePagesSection.classList.remove('hidden');
			if (currentPages < minPagesFromFiles) {
				totalPrintablePagesField.value = String(minPagesFromFiles);
			}
			return;
		}

		// If only photos remain, still hide section and set to 0
		printablePagesSection.classList.add('hidden');
		totalPrintablePagesField.value = '0';
	}

	function updateSuggestedPages() {
		if (!suggestedPagesHint) {
			return;
		}
		suggestedPagesHint.textContent =
			suggestedFilesLabel + ': ' + suggestedPages();
	}

	function renderTextPreview() {
		textPreview.innerHTML = '';
		renderExistingAttachments();
		var files = selectedTextFiles;
		if (!files.length && existingAttachments.filter(function(a){return a.type==='text';}).length === 0) {
			textPreview.innerHTML = '<p class="text-xs text-gray-500">No text files selected.</p>';
			return;
		}
		files.forEach(function (file, index) {
			var row = document.createElement('div');
			row.className = 'upload-file-row';
			var badge = document.createElement('span');
			badge.className = 'upload-file-badge';
			badge.textContent = extensionBadge(ext(file.name));
			var name = document.createElement('span');
			name.className = 'upload-file-name';
			name.textContent = file.name;
			var size = document.createElement('span');
			size.className = 'upload-file-size';
			size.textContent = formatBytes(file.size);
			var removeBtn = document.createElement('button');
			removeBtn.type = 'button';
			removeBtn.className = 'upload-item-remove';
			removeBtn.textContent = 'Remove';
			removeBtn.addEventListener('click', function () {
				console.log('[removeBtn] Removing file', file.name, 'at index', index);
				removeFileAt(textFilesField, index);
			});
			row.appendChild(badge);
			row.appendChild(name);
			row.appendChild(size);
			row.appendChild(removeBtn);
			textPreview.appendChild(row);
		});
	}

	function renderPhotoPreview() {
		photoPreview.innerHTML = '';
		renderExistingAttachments();
		var files = selectedPhotoFiles;
		if (!files.length && existingAttachments.filter(function(a){return a.type==='photo';}).length === 0) {
			photoPreview.innerHTML = '<p class="text-xs text-gray-500 col-span-3">No photos selected.</p>';
			return;
		}
		files.forEach(function (file, index) {
			var wrapper = document.createElement('div');
			wrapper.className = 'upload-photo-card';
			var image = document.createElement('img');
			image.className = 'upload-photo-thumb';
			image.alt = file.name;
			image.src = URL.createObjectURL(file);
			var meta = document.createElement('p');
			meta.className = 'upload-photo-meta';
			meta.textContent = file.name;
			var removeBtn = document.createElement('button');
			removeBtn.type = 'button';
			removeBtn.className = 'upload-photo-remove';
			removeBtn.textContent = 'x';
			removeBtn.setAttribute('aria-label', 'Remove image ' + file.name);
			removeBtn.addEventListener('click', function () {
				console.log('[removeBtn] Removing photo', file.name, 'at index', index);
				removeFileAt(photoFilesField, index);
			});
			wrapper.appendChild(image);
			wrapper.appendChild(removeBtn);
			wrapper.appendChild(meta);
			photoPreview.appendChild(wrapper);
		});
	}

	function removeFileAt(input, indexToRemove) {
		var files = input === textFilesField
			? selectedTextFiles
			: selectedPhotoFiles;
		if (indexToRemove < 0 || indexToRemove >= files.length) {
			return;
		}
		files.splice(indexToRemove, 1);
		console.log('[removeFileAt] Removed file at', indexToRemove, 'input:', input.name, 'remaining:', files.length, 'selectedTextFiles:', selectedTextFiles.length, 'selectedPhotoFiles:', selectedPhotoFiles.length);
		syncInputFiles(input, files);
		syncPrintablePagesState();
	}

	function syncInputFiles(input, files) {
		var dt = new DataTransfer();
		files.forEach(function (file) {
			dt.items.add(file);
		});
		input.files = dt.files;
		debugLog('syncInputFiles', {
			inputName: input.name,
			intendedCount: files.length,
			actualCount: (input.files || []).length,
			fileNames: Array.from(input.files || []).map(function (f) {
				return f.name;
			}),
		});
		onInputsChanged();
		renderTextPreview();
		renderPhotoPreview();
	}

	function appendFiles(input, incomingFiles) {
		var target = input === textFilesField
			? selectedTextFiles
			: selectedPhotoFiles;
		incomingFiles.forEach(function (file) {
			target.push(file);
		});
		debugLog('appendFiles', {
			inputName: input.name,
			incomingCount: incomingFiles.length,
			targetCount: target.length,
		});
		syncInputFiles(input, target);
	}

	function bindDropzone(zone, input) {
		if (!zone || !input) {
			return;
		}

		function openPicker() {
			input.click();
		}

		function applyDroppedFiles(event) {
			event.preventDefault();
			zone.classList.remove('is-dragover');
			var dropped = event.dataTransfer && event.dataTransfer.files;
			if (!dropped || !dropped.length) {
				return;
			}
			appendFiles(input, Array.from(dropped));
		}

		zone.addEventListener('click', openPicker);
		zone.addEventListener('keydown', function (event) {
			if (event.key === 'Enter' || event.key === ' ') {
				event.preventDefault();
				openPicker();
			}
		});
		zone.addEventListener('dragover', function (event) {
			event.preventDefault();
			zone.classList.add('is-dragover');
		});
		zone.addEventListener('dragleave', function () {
			zone.classList.remove('is-dragover');
		});
		zone.addEventListener('drop', applyDroppedFiles);
	}

	function safeDateFromInput(value) {
		if (!value) {
			return null;
		}
		var date = new Date(value + 'T00:00:00');
		if (isNaN(date.getTime())) {
			return null;
		}
		return date;
	}

	function yearsCharge(deliveryDate) {
		if (!deliveryDate) {
			return 0;
		}
		var now = new Date();
		var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
		if (deliveryDate <= today) {
			return 0;
		}
		var years = deliveryDate.getFullYear() - today.getFullYear();
		var candidate = new Date(today);
		candidate.setFullYear(today.getFullYear() + years);
		if (candidate < deliveryDate) {
			years += 1;
		}
		return Math.max(0, years);
	}

	function validateClient() {
		var errors = [];
		var textFiles = selectedTextFiles;
		var photoFiles = selectedPhotoFiles;
		var totalTextFiles = currentExistingTextFilesCount() + textFiles.length;
		var totalPhotoFiles = currentExistingPhotoFilesCount() + photoFiles.length;
		var printablePages = parseInt(totalPrintablePagesField.value || '0', 10);

		if (totalTextFiles > maxTextFiles) {
			errors.push('You can upload up to ' + maxTextFiles + ' text files.');
		}
		if (totalPhotoFiles > maxPhotoFiles) {
			errors.push('You can upload up to ' + maxPhotoFiles + ' photos.');
		}

		if (isNaN(printablePages) || printablePages < 0) {
			errors.push('Total printable pages must be 0 or greater.');
		}

		textFiles.forEach(function (file) {
			if (textExts.indexOf(ext(file.name)) < 0) {
				errors.push('Unsupported text file: ' + file.name);
			}
			if (file.size > maxFileSizeMb * 1024 * 1024) {
				errors.push(file.name + ' exceeds ' + maxFileSizeMb + 'MB.');
			}
		});

		photoFiles.forEach(function (file) {
			if (photoExts.indexOf(ext(file.name)) < 0) {
				errors.push('Unsupported photo file: ' + file.name);
			}
			if (file.size > maxFileSizeMb * 1024 * 1024) {
				errors.push(file.name + ' exceeds ' + maxFileSizeMb + 'MB.');
			}
		});

		if (
			!messageField.value.trim()
			&& totalTextFiles === 0
			&& totalPhotoFiles === 0
		) {
			errors.push('Provide message text or upload at least one file.');
		}

		var deliveryDate = safeDateFromInput(deliveryDateField.value);
		if (deliveryDate) {
			var now = new Date();
			var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
			var maxDate = new Date(today);
			maxDate.setFullYear(today.getFullYear() + maxDeliveryYears);
			if (deliveryDate < today) {
				errors.push('Delivery date cannot be in the past.');
			}
			if (deliveryDate > maxDate) {
				errors.push('Delivery date must be within ' + maxDeliveryYears + ' years.');
			}
		}

		setErrors(errors);
		debugLog('Validate client', {
			errors: errors,
			totalTextFiles: totalTextFiles,
			totalPhotoFiles: totalPhotoFiles,
			printablePages: printablePages,
			action: submitActionField ? submitActionField.value : '(missing)',
		});
		return errors.length === 0;
	}

	function recalcTotal() {
		var countryId = (countryField.value || '').trim();
		var country = countries[countryId];
		if (!country) {
			totalPriceNode.textContent = '$0.00';
			breakdownNode.textContent = '';
			debugLog('Recalc skipped: country missing', {
				countryId: countryId,
				countriesKeys: Object.keys(countries),
			});
			return;
		}

		var photoFiles = selectedPhotoFiles;
		var totalPhotoFiles = currentExistingPhotoFilesCount() + photoFiles.length;
		var totalPrintablePages = parseInt(
			totalPrintablePagesField.value || '0',
			10
		);
		if (isNaN(totalPrintablePages) || totalPrintablePages < 0) {
			totalPrintablePages = 0;
		}
		var photos = totalPhotoFiles;
		var years = yearsCharge(safeDateFromInput(deliveryDateField.value));

		var base = parseFloat(country.price || '0');

		var total = base;
		total += extraPagePrice * totalPrintablePages;
		total += extraPhotoPrice * photos;
		total += extraYearPrice * years;

		totalPriceNode.textContent = '$' + total.toFixed(2);
		breakdownNode.textContent =
			'Base $' + base.toFixed(2) +
			' + pages(' + totalPrintablePages + ')' +
			' + photos(' + photos + ')' +
			' + years(' + years + ')';

		debugLog('Recalc total', {
			countryId: countryId,
			country: country,
			base: base,
			totalPrintablePages: totalPrintablePages,
			photos: photos,
			years: years,
			extraPagePrice: extraPagePrice,
			extraPhotoPrice: extraPhotoPrice,
			extraYearPrice: extraYearPrice,
			total: total,
		});
	}

	function parseMoney(text) {
		var numeric = (text || '').replace(/[^0-9.-]/g, '');
		var parsed = parseFloat(numeric);
		return isNaN(parsed) ? 0 : parsed;
	}

	function onInputsChanged() {
		syncPrintablePagesState();
		updateSuggestedPages();
		validateClient();
		recalcTotal();
	}

	function hidePaidEditConfirmModal() {
		if (!paidEditConfirmModal) {
			return;
		}
		paidEditConfirmModal.classList.add('hidden');
		paidEditConfirmModal.classList.remove('flex');
	}

	function showPaidEditConfirmModal(message) {
		if (!paidEditConfirmModal || !paidEditConfirmText) {
			return;
		}
		paidEditConfirmText.textContent = message;
		paidEditConfirmModal.classList.remove('hidden');
		paidEditConfirmModal.classList.add('flex');
	}

	function hidePaidEditBalanceModal() {
		if (!paidEditBalanceModal) {
			return;
		}
		paidEditBalanceModal.classList.add('hidden');
		paidEditBalanceModal.classList.remove('flex');
	}

	function showPaidEditBalanceModal(message) {
		if (!paidEditBalanceModal || !paidEditBalanceText) {
			return;
		}
		paidEditBalanceText.textContent = message;
		paidEditBalanceModal.classList.remove('hidden');
		paidEditBalanceModal.classList.add('flex');
	}

	bindDropzone(textDropzone, textFilesField);
	bindDropzone(photoDropzone, photoFilesField);

	if (payNowButton && submitActionField) {
		payNowButton.addEventListener('click', function (event) {
			var selectedAction = isPaidEditMode ? 'draft' : 'pay';
			submitActionField.value = selectedAction;
			debugLog('Submit action selected', { action: selectedAction });

			if (!isPaidEditMode) {
				return;
			}

			event.preventDefault();
			syncInputFiles(textFilesField, selectedTextFiles);
			syncInputFiles(photoFilesField, selectedPhotoFiles);
			if (!validateClient()) {
				return;
			}

			var newTotal = parseMoney(totalPriceNode.textContent);
			var delta = newTotal - originalTotalPrice;
			var resultingBalance = currentBalance - delta;

			if (delta > 0 && currentBalance < delta) {
				showPaidEditBalanceModal(
					'Required: $' + delta.toFixed(2) +
					'. Available: $' + currentBalance.toFixed(2) + '.'
				);
				return;
			}

			var deltaText = 'No pricing difference.';
			if (delta > 0) {
				deltaText =
					'Additional charge $' + delta.toFixed(2) +
					' will be deducted.';
			} else if (delta < 0) {
				deltaText =
					'Refund $' + (-delta).toFixed(2) +
					' will be credited to your balance.';
			}
			var priceDifference = Math.abs(delta).toFixed(2);

			showPaidEditConfirmModal(
				'Old total: $' + originalTotalPrice.toFixed(2) +
				' | New total: $' + newTotal.toFixed(2) + '. ' +
				'Price difference: $' + priceDifference + '. ' +
				deltaText +
				' Resulting balance: $' + resultingBalance.toFixed(2) + '.'
			);
		});
	}
	if (saveDraftButton && submitActionField) {
		saveDraftButton.addEventListener('click', function () {
			submitActionField.value = 'draft';
			debugLog('Submit action selected', { action: 'draft' });
		});
	}

	textFilesField.addEventListener('change', function () {
		appendFiles(textFilesField, Array.from(textFilesField.files || []));
	});

	photoFilesField.addEventListener('change', function () {
		appendFiles(photoFilesField, Array.from(photoFilesField.files || []));
	});

	if (totalPrintablePagesField) {
		totalPrintablePagesField.addEventListener('input', function () {
			onInputsChanged();
		});
	}

	countryField.addEventListener('change', onInputsChanged);
	deliveryDateField.addEventListener('change', function () {
		onInputsChanged();
	});
	messageField.addEventListener('input', onInputsChanged);
	existingAttachmentDeleteCheckboxes.forEach(function (checkbox) {
		checkbox.addEventListener('change', onInputsChanged);
	});

	if (paidEditConfirmBtn) {
		paidEditConfirmBtn.addEventListener('click', function () {
			hidePaidEditConfirmModal();
			submitActionField.value = 'draft';
			form.requestSubmit();
		});
	}

	if (paidEditCancelBtn) {
		paidEditCancelBtn.addEventListener('click', hidePaidEditConfirmModal);
	}

	if (paidEditBalanceCloseBtn) {
		paidEditBalanceCloseBtn.addEventListener(
			'click',
			hidePaidEditBalanceModal
		);
	}

	form.addEventListener('submit', function (event) {
		var submitter = event.submitter || null;
		if (submitter && submitter.dataset && submitter.dataset.submitAction) {
			submitActionField.value = submitter.dataset.submitAction;
		}
		if (isPaidEditMode && !submitActionField.value) {
			submitActionField.value = 'draft';
		}
		syncInputFiles(textFilesField, selectedTextFiles);
		syncInputFiles(photoFilesField, selectedPhotoFiles);
		debugLog('Form submit', {
			action: submitActionField ? submitActionField.value : '(missing)',
			textFiles: selectedTextFiles.map(function (f) { return f.name; }),
			photoFiles: selectedPhotoFiles.map(function (f) { return f.name; }),
			countryId: countryField.value,
			printablePages: totalPrintablePagesField.value,
			deliveryDate: deliveryDateField.value,
		});
		if (!validateClient()) {
			event.preventDefault();
			debugLog('Submit prevented by client validation');
		}
	});

	renderTextPreview();
	renderPhotoPreview();
	onInputsChanged();
}());
