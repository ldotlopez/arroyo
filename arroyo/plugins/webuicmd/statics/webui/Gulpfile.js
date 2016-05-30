
var SERVER = "127.0.0.1:5000";

var gulp = require('gulp'),
    watch = require('gulp-watch'),
    browserSync = require('browser-sync').create(),
    clean = require('gulp-clean'),
    typescript = require('gulp-tsc'),
    sass = require('gulp-sass'),
    autoprefixer = require('gulp-autoprefixer')
    cleanCss = require('gulp-clean-css');

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
               .pipe(gulp.dest(paths.dist.root))
               .pipe(browserSync.stream());
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
               .pipe(gulp.dest(paths.dist.app))
               .pipe(browserSync.stream());
});

gulp.task('styles', function() {
    return gulp.src(paths.src.styles)
               .pipe(sass())
               .pipe(autoprefixer())
               .pipe(cleanCss())
               .pipe(gulp.dest(paths.dist.styles))
               .pipe(browserSync.stream());
});

gulp.task('fonts', function() {
    return gulp.src(paths.src.fonts)
               .pipe(gulp.dest(paths.dist.fonts));
});

gulp.task('watch', function() {
    gulp.watch(paths.src.styles, ['styles']);
    gulp.watch(paths.src.typescript, ['compile-typescript']);
    gulp.watch(paths.src.static, ['copy']);
});

gulp.task('browser-sync', function() {
    browserSync.init({
        proxy: SERVER
    });
});

gulp.task('build', ['copy', 'compile-typescript', 'styles', 'fonts']);
gulp.task('dev', ['build', 'watch', 'browser-sync']);
gulp.task('default', ['build']);
