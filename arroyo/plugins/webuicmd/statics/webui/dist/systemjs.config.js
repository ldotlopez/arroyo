
(function(global) {
    // map tells the System loader where to look for things
    var map = {
        'app':                        global.STATIC_URL + 'app',
        '@angular':                   global.STATIC_URL + 'node_modules/@angular',
        'angular2-in-memory-web-api': global.STATIC_URL + 'node_modules/angular2-in-memory-web-api',
        'rxjs':                       global.STATIC_URL + 'node_modules/rxjs'
    };

    // packages tells the System loader how to load when no filename and/or no extension
    var packages = {
        'app':                        { main: 'main.js',  defaultExtension: 'js' },
        'rxjs':                       { defaultExtension: 'js' },
        'angular2-in-memory-web-api': { defaultExtension: 'js' },
    };

    var ngPackageNames = [
        'common',
        'compiler',
        'core',
        'http',
        'platform-browser',
        'platform-browser-dynamic',
        'router',
        'router-deprecated',
        'upgrade',
    ];

    // Add package entries for angular packages
    ngPackageNames.forEach(function(pkgName) {
        packages['@angular/'+pkgName] = { main: pkgName + '.umd.js', defaultExtension: 'js' };
    });

    var config = {
        map: map,
        packages: packages
    }

    System.config(config);
})(this);
