'use strict';

/* App module */

var arroyoApp = angular.module('arroyoApp', [
  'ngRoute',
  'arroyoControllers',
  'arroyoFilters'
]);

arroyoApp.config(['$routeProvider', '$compileProvider', function($routeProvider, $compileProvider) {
	$routeProvider
			.when('/search', {
				templateUrl: 'partials/search.html',
				controller: 'searchCtrl'
			})
			.when('/downloads', {
				templateUrl: 'partials/downloads.html',
				controller: 'downloadsCtrl'
			})
			.when('/explore/movies/', {
				templateUrl: 'partials/explore.html',
				controller: 'exploreCtrl'
			})
			.otherwise({
				redirectTo: '/search'
			});

	$compileProvider
		.aHrefSanitizationWhitelist(/^\s*(https?|ftp|mailto|magnet):/);
}]);
