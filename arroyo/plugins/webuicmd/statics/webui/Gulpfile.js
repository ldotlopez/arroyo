
var gulp = require('gulp'),
    clean = require('gulp-clean'),
    typescript = require('gulp-tsc'),
    sass = require('gulp-sass'),
    autoprefixer = require('gulp-autoprefixer');

var paths = require('./build/paths');


// FIXME
// We are serving dev node-modules in dist, so wiping the
// directory removes the symlink and breaks the build.

// gulp.task('clean', function() {
//     return gulp.src(paths.dist.root + "/**/*", {read: false})
//                .pipe(clean());
// });


gulp.task('copy', function() {
    return gulp.src(paths.src.static)
               .pipe(gulp.dest(paths.dist.root));
})

gulp.task('compile-typescript', function() {
    const conf = {
        outDir: paths.dist.app,
        target: "es5",
        module: "commonjs",
        moduleResolution: "node",
        sourceMap: true,
        emitDecoratorMetadata: true,
        experimentalDecorators: true,
        removeComments: false,
        noImplicitAny: false
    };

    return gulp.src(paths.src.typescript)
               .pipe(typescript(conf))
               .pipe(gulp.dest(paths.dist.app));
});

gulp.task('styles', function() {
    return gulp.src(paths.src.styles)
               .pipe(sass())
               .pipe(autoprefixer())
               .pipe(gulp.dest(paths.dist.styles));
});

gulp.task('build', ['copy', 'compile-typescript', 'styles']);
gulp.task('default', ['build']);
