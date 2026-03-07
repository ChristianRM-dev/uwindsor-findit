(function () {
  function initPreview() {
    var input = document.getElementById("id_photos");
    var grid = document.getElementById("photo-preview-grid");
    var meta = document.getElementById("photo-preview-meta");
    var maxFiles = 5;
    var selectedFiles = [];

    if (!input || !grid || !meta) {
      return;
    }

    function syncInputFiles() {
      if (typeof DataTransfer === "undefined") {
        return;
      }

      var transfer = new DataTransfer();
      selectedFiles.forEach(function (file) {
        transfer.items.add(file);
      });
      input.files = transfer.files;
    }

    function updateMeta() {
      if (selectedFiles.length === 0) {
        meta.textContent = "";
        return;
      }

      if (selectedFiles.length > maxFiles) {
        meta.textContent = "You selected " + selectedFiles.length + " files. Max allowed is " + maxFiles + ". Remove extras before submitting.";
      } else {
        meta.textContent = selectedFiles.length + " photo(s) selected.";
      }
    }

    function renderPreview() {
      grid.innerHTML = "";

      selectedFiles.forEach(function (file, index) {
        var col = document.createElement("div");
        col.className = "col-6 col-md-4 col-lg-3";

        var card = document.createElement("div");
        card.className = "border rounded p-2 bg-white h-100 d-flex flex-column";

        var image = document.createElement("img");
        image.className = "img-fluid rounded";
        image.alt = file.name;
        image.src = URL.createObjectURL(file);
        image.onload = function () {
          URL.revokeObjectURL(image.src);
        };

        var caption = document.createElement("div");
        caption.className = "small text-muted text-truncate mt-1";
        caption.title = file.name;
        caption.textContent = file.name;

        var removeLink = document.createElement("a");
        removeLink.href = "#";
        removeLink.className = "small link-danger mt-1";
        removeLink.textContent = "Remove";
        removeLink.addEventListener("click", function (event) {
          event.preventDefault();
          selectedFiles.splice(index, 1);
          syncInputFiles();
          updateMeta();
          renderPreview();
        });

        card.appendChild(image);
        card.appendChild(caption);
        card.appendChild(removeLink);
        col.appendChild(card);
        grid.appendChild(col);
      });
    }

    input.addEventListener("change", function () {
      selectedFiles = Array.prototype.slice.call(input.files || []);
      syncInputFiles();
      updateMeta();
      renderPreview();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPreview);
  } else {
    initPreview();
  }
})();
