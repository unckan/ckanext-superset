$(document).ready(function() {
    // Toggle info row
    $('.superset-toggle-info').on('click', function(e) {
        e.preventDefault();
        var chartId = $(this).data('chart-id');
        $('#chart-info-' + chartId).toggle();
        $(this).find('i').toggleClass('fa-plus-circle fa-minus-circle');
    });

    // Filters
    var $vizFilter = $('#superset-viz-filter');
    var $ckanFilter = $('#superset-ckan-filter');
    var $table = $('#superset-charts-table');

    function filterCharts() {
        var selectedTypes = $vizFilter.val() || [];
        var ckanVal = $ckanFilter.val();

        $table.find('tr[data-viz-type]').each(function() {
            var vizType = $(this).data('viz-type');
            var hasCkan = $(this).attr('data-has-ckan') === 'true';

            // Skip info rows — they stay hidden until toggled
            if (this.id && this.id.indexOf('chart-info-') === 0) {
                return;
            }

            var matchType = selectedTypes.length === 0 || selectedTypes.indexOf(vizType) !== -1;
            var matchCkan = ckanVal === 'all' || (ckanVal === 'with' && hasCkan) || (ckanVal === 'without' && !hasCkan);

            if (matchType && matchCkan) {
                $(this).show();
            } else {
                $(this).hide();
                // Also hide the info row if the main row is hidden
                var chartId = $(this).find('.superset-toggle-info').data('chart-id');
                if (chartId) {
                    $('#chart-info-' + chartId).hide();
                }
            }
        });
    }

    $vizFilter.on('change', filterCharts);
    $ckanFilter.on('change', filterCharts);

    // Apply default filter on load
    filterCharts();
});