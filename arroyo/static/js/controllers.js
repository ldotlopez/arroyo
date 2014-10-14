'use strict';

/* Controllers module */

var arroyoControllers = angular.module('arroyoControllers', []);

arroyoControllers.controller('searchCtrl', ['$scope', '$http', '$filter',
	function($scope, $http, $filter) {
		$scope.types = {};
		$scope.languages = {}
        $scope.all_states = false;

		/* Fill types and language models */
		$http.get('/introspect/').success(function(data) {
			$scope.types = [];
			data.types.forEach(function (e) {
				$scope.types.push({name: e, selected: false});
			});
			$scope.languages = [];
			data.languages.forEach(function (e) {
				$scope.languages.push({name: e, selected: false});
			});
		});

		/* Perform a query and update results */
		$scope.search = function () {
			if ($scope.query == undefined ||
			    $scope.query.length < 3) {
				$scope.results = [];
				$scope.resultsGroups = [];
				return;
			}

			var query = 'q='+$scope.query;
            if ($scope.all_states) {
                query += '&all_states';
			}
            $scope.types.forEach(function(e) {
				if (e.selected) {
					query += '&type='+e.name;
				}
			});
			$scope.languages.forEach(function(e) {
				if (e.selected) {
					query += '&language='+e.name;
				}
			});

			$http.get('/search/?'+query).success(function(data) {
				$scope.results = data;
				/* 
				FIXME: Ugly hack, using this filter in the HTML in conjuction with ng-repeat is
				_very_ slow.
				*/
				$scope.resultsGroups = $scope.itemsGrouped = $filter('groupByBlock')(data, 3);
				
			});
		};

		$scope.addDownload = function(id) {
			$http.post('/downloads/', {'id': id})
				.success(function(data) {
					console.log("Item: "+id+" added");
				})
				.error(function(data, status) {
					console.log("Error adding "+id+": "+data.msg);
				});
		};
}]);


arroyoControllers.controller('downloadsCtrl', ['$scope', '$http', function($scope, $http) {
	$scope.downloads = {};

	$http.get('/downloads/').success(function(data) {
		$scope.downloads = {};
		data.forEach(function(element) {
			$scope.downloads[element.id] = element;
		});
	});

	$scope.removeDownload = function(id) {
		$http.delete('/downloads/'+id)
			.success(function(data) {
				delete $scope.downloads[id];
				console.log("Item: "+id+" removed");
			})
			.error(function(data, status) {
				console.log("Error removing "+id+": "+data.msg);
			});
	};
	
}]);

arroyoControllers.controller('exploreCtrl', ['$scope', function ($scope) {

}]);
