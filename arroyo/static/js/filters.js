'use strict';

/* Filters module */

var arroyoFilters = angular.module('arroyoFilters', []);

/* Don't use this */
arroyoFilters.filter('groupByBlock', function() {	
	return function(input, blockSize) {
		if (input === undefined) return [];
	
		if (input.length == 0 || !blockSize)
			return [input];	

		var ret = [];
		var idx = 0;
		do  {
			var start = idx * blockSize;
			var end = start + blockSize;
			ret[idx++] = input.slice(start, end);
		} while (start <= input.length);

		return ret;

	};
});
