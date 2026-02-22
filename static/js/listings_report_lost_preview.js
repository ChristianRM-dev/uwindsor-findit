(function () {
  function initPreview() {
    var input = document.getElementById("id_photos");
    var grid = document.getElementById("photo-preview-grid");
    var meta = document.getElementById("photo-preview-meta");

    if (!input || !grid || !meta) {
      return;
    }

    input.addEventListener("change", function () {
      var files = Array.prototype.slice.call(input.files || []);
      var maxFiles = 5;

      grid.innerHTML = "";

      if (files.length === 0) {
        meta.textContent = "";
        return;
      }

      if (files.length > maxFiles) {
        meta.textContent = "You selected " + files.length + " files. Only first " + maxFiles + " are previewed.";
      } else {
        meta.textContent = files.length + " photo(s) selected.";
      }

      files.slice(0, maxFiles).forEach(function (file) {
        var col = document.createElement("div");
        col.className = "col-6 col-md-4 col-lg-3";

        var card = document.createElement("div");
        card.className = "border rounded p-2 bg-white h-100";

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

        card.appendChild(image);
        card.appendChild(caption);
        col.appendChild(card);
        grid.appendChild(col);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPreview);
  } else {
    initPreview();
  }
})();
