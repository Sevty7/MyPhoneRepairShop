// Order Form - Dynamic Parts Management
(function() {
  document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('parts-container');
    const addPartBtn = document.getElementById('add-part-btn');
    
    if (!addPartBtn) return;

    // Функция обновления цены
    function updatePrice(selectElement) {
        // Находим выбранную опцию
        const option = selectElement.options[selectElement.selectedIndex];
        // Получаем цену из data-price
        const price = option.getAttribute('data-price');
        
        // Находим поле ввода цены в той же строке
        const row = selectElement.closest('.part-item');
        const priceInput = row.querySelector('.part-price');
        
        // Устанавливаем значение
        if (priceInput && price) {
            priceInput.value = parseFloat(price).toFixed(2);
        }
    }

    // Слушатель изменений (делегирование событий для динамических элементов)
    container.addEventListener('change', function(e) {
        if (e.target.classList.contains('part-select')) {
            updatePrice(e.target);
        }
    });

    addPartBtn.addEventListener('click', function() {
      const template = document.getElementById('part-template');
      const newPart = template.cloneNode(true);
      newPart.removeAttribute('id');
      newPart.classList.remove('d-none');
      newPart.querySelectorAll('select, input').forEach(el => el.disabled = false);
      container.appendChild(newPart);
    });

    container.addEventListener('click', function(e) {
      if (e.target.closest('.remove-part-btn')) {
        e.target.closest('.part-item').remove();
      }
    });
  });
})();