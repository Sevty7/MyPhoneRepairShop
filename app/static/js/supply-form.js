// Supply Form - Dynamic Items Management
(function() {
  document.addEventListener('DOMContentLoaded', function() {
    const addSupplyItemBtn = document.getElementById('add-supply-item-btn');
    if (!addSupplyItemBtn) return;

    addSupplyItemBtn.addEventListener('click', function() {
      const container = document.getElementById('supply-parts-container');
      const template = document.getElementById('supply-item-template');
      const newItem = template.cloneNode(true);
      newItem.removeAttribute('id');
      newItem.classList.remove('d-none');
      // Enable inputs for the new element
      newItem.querySelectorAll('input').forEach(el => el.disabled = false);
      container.appendChild(newItem);
    });

    document.getElementById('supply-parts-container').addEventListener('click', function(e) {
      if (e.target.closest('.remove-item-btn')) {
        e.target.closest('.supply-item').remove();
      }
    });
  });
})();
