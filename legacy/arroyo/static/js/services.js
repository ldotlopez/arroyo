'use strict';

/* Services */

var titaServices = angular.module('titaServices', ['ngResource']);

titaServices.factory('Search', ['$resource', 
	function ($resource) {
		console.log($q);
		return $resource('/search', {}, {
			query: {method: 'GET', params: {'name_like': '*S..E..*'}, isArray: true}
		});
	}
]);
